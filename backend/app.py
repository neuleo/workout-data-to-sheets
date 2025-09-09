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
Analysiere die folgenden Bilder von einem Fitness-Tracker, die alle zum selben Workout gehören.
Fasse die Daten aus ALLEN Bildern zu einem einzigen, zusammenhängenden Bericht zusammen.
Erstelle eine übersichtliche Liste aller relevanten Datenpunkte (wie z.B. Dauer, Kalorien, Herzfrequenzzonen, Distanz, etc.).
Wenn Daten auf mehreren Bildern erscheinen (z.B. die Gesamtdauer), präsentiere sie nur einmal im finalen Bericht.
Ziel ist es, eine vollständige Zusammenfassung des gesamten Workouts zu erstellen, als ob alle Daten von einem einzigen Bildschirm kämen.
"""
        
        print(f"--> [LOG] Sende Anfrage an die Gemini API für die Analyse von {len(images)} Bildern...")
        
        # Create the content list for the Gemini API
        content = [prompt]
        content.extend(images)
        
        response = gemini_model.generate_content(content)
        
        print("--- DETAILLIERTE BILDANALYSE (ZUSAMMENFASSUNG) ---")
        print(response.text)
        print("-------------------------------------------------")

        # Erfolgsmeldung mit dem Analyse-Text zurückgeben
        return jsonify({
            "message": f"Analyse von {len(images)} Bildern abgeschlossen.",
            "full_text": response.text
        }), 200

    except Exception as e:
        print(f"--> [LOG] FEHLER bei der Bildverarbeitung oder beim Upload: {e}")
        return jsonify({"error": f"Ein interner Fehler ist aufgetreten: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)