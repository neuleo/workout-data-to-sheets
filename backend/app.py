import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import io

app = Flask(__name__)
CORS(app)

# --- Google Sheets Konfiguration ---
SPREADSHEET_NAME = os.environ.get('SPREADSHEET_NAME')
WORKSHEET_NAME = 'Workouts'
SERVICE_ACCOUNT_FILE = '/app/service-account.json'
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

# --- Gemini API Konfiguration ---
try:
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY nicht in der Umgebung gefunden.")
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
except ValueError as e:
    print(f"Fehler bei der Gemini-Konfiguration: {e}")
    gemini_model = None

def get_sheet():
    print("--> [LOG] Versuche, eine Verbindung zu Google Sheets herzustellen...")
    if not SPREADSHEET_NAME:
        print("--> [LOG] FEHLER: SPREADSHEET_NAME ist in der Umgebung nicht gesetzt.")
        return None
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPE)
        client = gspread.authorize(creds)
        
        # Versuche, das Spreadsheet zu öffnen, oder erstelle es, wenn es nicht existiert
        try:
            spreadsheet = client.open(SPREADSHEET_NAME)
        except gspread.SpreadsheetNotFound:
            print(f"--> [LOG] Spreadsheet '{SPREADSHEET_NAME}' nicht gefunden. Es wird versucht, es zu erstellen...")
            spreadsheet = client.create(SPREADSHEET_NAME)
            # Teile das neue Sheet mit der Service-Account-E-Mail, um Schreibzugriff zu gewährleisten
            spreadsheet.share(creds.service_account_email, perm_type='user', role='writer')

        # Versuche, das Worksheet zu öffnen, oder erstelle es, wenn es nicht existiert
        try:
            sheet = spreadsheet.worksheet(WORKSHEET_NAME)
        except gspread.WorksheetNotFound:
            print(f"--> [LOG] Worksheet '{WORKSHEET_NAME}' nicht gefunden. Es wird erstellt...")
            sheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows="100", cols="20")

        print("--> [LOG] Erfolgreich mit Google Sheets verbunden.")
        return sheet
    except Exception as e:
        print(f"--> [LOG] FEHLER bei der Google Sheets-Authentifizierung oder Blatterstellung: {e}")
        return None

# Definitive Header-Reihenfolge für das Google Sheet
SHEET_HEADERS = [
    'WorkoutType', 'Date', 'TotalTime', 'TotalCalories', 'AvgHeartRate', 'MaxHeartRate', 'Device',
    'ExerciseName', 'ExerciseTime', 'Reps', 'Sets', 'ExerciseCalories', 'ExerciseAvgHR', 'ExerciseMaxHR',
    'PauseDuration', 'PauseFrom', 'PauseTo',
    'TotalDistance_km', 'EstimatedFluidLoss_ml',
    'Interval', 'IntervalType', 'IntervalDuration', 'IntervalDistance_km', 'IntervalAvgHR',
    'Activity', 'SwimDistance_m', 'AvgPace_per_100m', 'TotalStrokes', 'SWOLF'
]

def flatten_json_for_sheet(data):
    rows = []
    base_data = data.get('summary', {})
    
    # Basisinformationen für jede Zeile
    base_row = {
        'WorkoutType': data.get('workoutType'),
        'Date': base_data.get('date'),
        'TotalTime': base_data.get('totalTime'),
        'TotalCalories': base_data.get('totalCalories'),
        'AvgHeartRate': base_data.get('avgHeartRate'),
        'MaxHeartRate': base_data.get('maxHeartRate'),
        'Device': base_data.get('device')
    }

    workout_type = data.get('workoutType')
    details = data.get('details', {})

    if workout_type == 'Krafttraining':
        if not details.get('exercises'):
             # Fallback für eine einzelne Zeile, wenn keine Übungen vorhanden sind
            rows.append(base_row)
        else:
            for exercise in details.get('exercises', []):
                row = base_row.copy()
                row.update({
                    'ExerciseName': exercise.get('name'),
                    'ExerciseTime': exercise.get('time'),
                    'Reps': exercise.get('reps'),
                    'Sets': exercise.get('sets'),
                    'ExerciseCalories': exercise.get('calories'),
                    'ExerciseAvgHR': exercise.get('avgHeartRate'),
                    'ExerciseMaxHR': exercise.get('maxHeartRate')
                })
                rows.append(row)
    
    elif workout_type == 'Laufen':
        base_row.update({
            'TotalDistance_km': details.get('totalDistance'),
            'EstimatedFluidLoss_ml': details.get('estimatedFluidLoss')
        })
        if not details.get('intervals'):
            rows.append(base_row)
        else:
            for interval in details.get('intervals', []):
                row = base_row.copy()
                row.update({
                    'Interval': interval.get('interval'),
                    'IntervalType': interval.get('type'),
                    'IntervalDuration': interval.get('duration'),
                    'IntervalDistance_km': interval.get('distance'),
                    'IntervalAvgHR': interval.get('avgHeartRate')
                })
                rows.append(row)

    elif workout_type == 'Schwimmen':
        base_row.update({
            'Activity': details.get('activity'),
            'SwimDistance_m': details.get('totalDistance'),
            'AvgPace_per_100m': details.get('avgPace'),
            'TotalStrokes': details.get('totalStrokes'),
            'SWOLF': details.get('swolf')
        })
        rows.append(base_row)
        
    else: # Fallback für unbekannte Typen
        rows.append(base_row)

    # Konvertiere die Liste von Dictionaries in eine Liste von Listen in der korrekten Reihenfolge
    final_rows = []
    for row_dict in rows:
        final_rows.append([row_dict.get(h) for h in SHEET_HEADERS])
        
    return final_rows


@app.route('/api/upload', methods=['POST'])
def upload_image():
    print("\n--- Neue Anfrage an /api/upload ---")
    if not gemini_model:
        return jsonify({"error": "Gemini API ist nicht konfiguriert."}), 500

    if 'files' not in request.files:
        return jsonify({"error": "Keine Dateien im Request gefunden."}),
    
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({"error": "Keine Dateien ausgewählt."}),

    images = []
    for file in files:
        try:
            images.append(Image.open(file.stream))
        except Exception as e:
            return jsonify({"error": f"Fehler beim Verarbeiten der Datei: {file.filename}"}), 400

    if not images:
        return jsonify({"error": "Keine gültigen Bilder gefunden."}),

    try:
        prompt = '''
Du bist ein Experte für die Analyse von Sportdaten. Deine Aufgabe ist es, die bereitgestellten Bilder von einer Fitnessuhr zu analysieren, den Workout-Typ zu identifizieren und alle Daten in ein strukturiertes JSON-Format zu extrahieren.

1.  **Workout-Typ identifizieren:** Bestimme zuerst, welcher der folgenden drei Workout-Typen dargestellt wird: 'Krafttraining', 'Laufen' oder 'Schwimmen'.

2.  **Daten extrahieren und JSON erstellen:** Fülle basierend auf dem identifizierten Typ die entsprechende JSON-Struktur aus.

**ANTWORTE AUSSCHLIESSLICH MIT DEM REINEN JSON-OBJEKT.** Füge keine Markdown-Formatierung (wie ```json ... ```) oder anderen erklärenden Text hinzu.

---
**JSON-Strukturen je nach Workout-Typ:**

**1. Wenn der Typ 'Krafttraining' ist:**
```json
{
  "workoutType": "Krafttraining",
  "summary": {
    "date": "YYYY-MM-DD oder null",
    "totalTime": "HH:MM:SS",
    "totalCalories": 216,
    "avgHeartRate": 110,
    "maxHeartRate": 139,
    "device": "Galaxy Watch 5 Pro oder null"
  },
  "details": {
    "totalExercises": 3,
    "exercises": [
      {
        "name": "Name der Übung",
        "time": "HH:MM:SS",
        "reps": 200,
        "sets": 4,
        "calories": 32,
        "avgHeartRate": 123,
        "maxHeartRate": 139
      }
    ],
    "pauses": [
      {
        "duration": "HH:MM:SS",
        "from": "Workout X",
        "to": "Workout Y"
      }
    ]
  }
}
```

**2. Wenn der Typ 'Laufen' ist:**
```json
{
  "workoutType": "Laufen",
  "summary": {
    "date": "YYYY-MM-DD oder null",
    "totalTime": "HH:MM:SS",
    "totalCalories": 286,
    "avgHeartRate": 147,
    "maxHeartRate": 177,
    "device": "Gerätename oder null"
  },
  "details": {
    "totalDistance": 3.33,
    "estimatedFluidLoss": 409,
    "intervals": [
      {"interval": "Nummer/Name", "type": "Workout/Erholung/Aufwärmen", "duration": "HH:MM:SS", "distance": 0.26, "avgHeartRate": 72}
    ],
    "heartRateZones": [
      {"zone": "Zonen-Name", "range": "BPM-Bereich"}
    ],
    "weather": {
      "temperature": 19.0
    }
  }
}
```

**3. Wenn der Typ 'Schwimmen' ist:**
```json
{
  "workoutType": "Schwimmen",
  "summary": {
    "date": "YYYY-MM-DD oder null",
    "totalTime": "HH:MM:SS",
    "totalCalories": 301,
    "avgHeartRate": 133,
    "maxHeartRate": 148,
    "device": "Galaxy Watch 5 Pro oder null"
  },
  "details": {
    "activity": "Brustschwimmen",
    "totalDistance": 800,
    "avgPace": "MM'SS"/100m",
    "totalStrokes": 70,
    "swolf": 70,
    "laps": [],
    "heartRateZones": [
        {"zone": "Zonen-Name", "range": "BPM-Bereich", "timePercentage": 79.4}
    ]
  }
}
```
---
Analysiere nun die folgenden Bilder und gib das entsprechende JSON zurück.
'''
        
        content = [prompt]
        content.extend(images)
        
        response = gemini_model.generate_content(content)
        
        print("--- ROH-ANTWORT VON GEMINI API ---")
        print(response.text)
        print("----------------------------------")

        try:
            cleaned_text = response.text.strip().replace('```json', '').replace('```', '')
            json_data = json.loads(cleaned_text)
            
            # --- Google Sheets Integration ---
            sheet = get_sheet()
            if sheet:
                print("--> [LOG] Verarbeite Daten für Google Sheets...")
                rows_to_add = flatten_json_for_sheet(json_data)
                
                # Überprüfe, ob das Sheet leer ist, um den Header hinzuzufügen
                if not sheet.get_all_records():
                    print("--> [LOG] Sheet ist leer. Füge Header-Zeile hinzu.")
                    sheet.append_row(SHEET_HEADERS, value_input_option='USER_ENTERED')
                
                print(f"--> [LOG] Füge {len(rows_to_add)} Zeile(n) zum Sheet hinzu.")
                sheet.append_rows(rows_to_add, value_input_option='USER_ENTERED')
                
                # Füge eine Erfolgsmeldung zum finalen JSON hinzu
                json_data['sheets_status'] = f'{len(rows_to_add)} Zeile(n) erfolgreich zu Google Sheets hinzugefügt.'
                print("--> [LOG] Daten erfolgreich an Google Sheets gesendet.")
            else:
                json_data['sheets_status'] = 'Fehler bei der Verbindung zu Google Sheets.'
                print("--> [LOG] Senden an Google Sheets fehlgeschlagen, siehe vorherige Fehler.")
            # --------------------------------

            return jsonify(json_data), 200
        except json.JSONDecodeError as e:
            return jsonify({"error": "Die Antwort der KI war kein gültiges JSON.", "raw_response": response.text}), 500

    except Exception as e:
        return jsonify({"error": f"Ein interner Fehler ist aufgetreten: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
