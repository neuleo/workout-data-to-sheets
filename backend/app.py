import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
# import gspread # Vorerst deaktiviert
# from oauth2client.service_account import ServiceAccountCredentials # Vorerst deaktiviert
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import io

app = Flask(__name__)
CORS(app)

# --- Google Sheets Konfiguration (VORERST DEAKTIVIERT) ---
# SPREADSHEET_NAME = 'WorkoutData'
# WORKSHEET_NAME = 'Sheet1'
# SERVICE_ACCOUNT_FILE = '/app/service-account.json'
# SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

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

# def get_sheet(): # Vorerst deaktiviert
#     print("--> [LOG] Versuche, eine Verbindung zu Google Sheets herzustellen...")
#     try:
#         creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPE)
#         client = gspread.authorize(creds)
#         sheet = client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)
#         print("--> [LOG] Erfolgreich mit Google Sheets verbunden.")
#         return sheet
#     except Exception as e:
#         print(f"--> [LOG] FEHLER bei der Google Sheets-Authentifizierung: {e}")
#         return None

@app.route('/api/upload', methods=['POST'])
def upload_image():
    print("\n--- Neue Anfrage an /api/upload ---")
    if not gemini_model:
        print("--> [LOG] Fehler: Gemini API ist nicht konfiguriert.")
        return jsonify({"error": "Gemini API ist nicht konfiguriert. Bitte überprüfen Sie den API-Schlüssel."}), 500

    if 'files' not in request.files:
        print("--> [LOG] Fehler: Keine Dateien im Request gefunden.")
        return jsonify({"error": "Keine Dateien im Request gefunden."}), 400

    files = request.files.getlist('files')

    if not files or all(f.filename == '' for f in files):
        print("--> [LOG] Fehler: Keine Dateien ausgewählt.")
        return jsonify({"error": "Keine Dateien ausgewählt."}), 400

    images = []
    file_names = []
    for file in files:
        if file and file.filename:
            print(f"--> [LOG] Datei empfangen: {file.filename}")
            file_names.append(file.filename)
            try:
                image = Image.open(file.stream)
                images.append(image)
            except Exception as e:
                print(f"--> [LOG] FEHLER beim Öffnen der Datei {file.filename}: {e}")
                return jsonify({"error": f"Fehler beim Verarbeiten der Datei: {file.filename}"}), 400

    if not images:
        print("--> [LOG] Fehler: Keine gültigen Bilder gefunden.")
        return jsonify({"error": "Keine gültigen Bilder gefunden."}), 400

    try:
        prompt = """
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
"""
        
        print(f"--> [LOG] Sende Anfrage an die Gemini API für die Analyse von {len(images)} Bildern...")
        
        content = [prompt]
        content.extend(images)
        
        response = gemini_model.generate_content(content)
        
        print("--- ROH-ANTWORT VON GEMINI API ---")
        print(response.text)
        print("----------------------------------")

        # Versuche, die Textantwort als JSON zu parsen
        try:
            # Entferne mögliche Markdown-Formatierungen
            cleaned_text = response.text.strip().replace('```json', '').replace('```', '')
            json_data = json.loads(cleaned_text)
            print("--> [LOG] JSON-Antwort erfolgreich geparst.")
            return jsonify(json_data), 200
        except json.JSONDecodeError as e:
            print(f"--> [LOG] FEHLER beim Parsen der JSON-Antwort: {e}")
            print(f"--> [LOG] Nicht-JSON-Antwort war: {response.text}")
            return jsonify({"error": "Die Antwort der KI war kein gültiges JSON.", "raw_response": response.text}), 500

    except Exception as e:
        print(f"--> [LOG] FEHLER bei der Bildverarbeitung oder API-Anfrage: {e}")
        return jsonify({"error": f"Ein interner Fehler ist aufgetreten: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)