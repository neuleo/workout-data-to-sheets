# Projektplan: Workout-Daten zu Google Sheets

## Phase 1: Projektstruktur und Docker Compose-Einrichtung (Dauer: ~1 Tag)

**Ziel:** Eine solide Basis für die Entwicklung schaffen, indem die Verzeichnisstruktur und die Docker-Compose-Konfiguration eingerichtet werden.

1.  **Verzeichnisstruktur anlegen:**
    ```
    samsung-health-data-extractor/
    ├── backend/
    │   ├── app.py
    │   ├── Dockerfile
    │   └── requirements.txt
    ├── frontend/
    │   ├── index.html
    │   └── Dockerfile
    ├── docker-compose.yml
    └── service-account.json
    ```

2.  **`docker-compose.yml` erstellen:**
    *   Definiere zwei Services: `backend` und `frontend`.
    *   Lege die Ports fest:
        *   `frontend`: `8080:80` (Host:Container)
        *   `backend`: `5000:5000`
    *   Binde das `backend`-Verzeichnis als Build-Kontext für den `backend`-Service ein.
    *   Binde das `frontend`-Verzeichnis als Build-Kontext für den `frontend`-Service ein.

3.  **API-Schlüssel vorbereiten:**
    *   Lege die `service-account.json`-Datei sicher im Hauptverzeichnis ab. Diese Datei wird später als Volume in den Backend-Container eingebunden, um die Authentifizierung gegenüber der Google Sheets API zu ermöglichen.

## Phase 2: Backend-Entwicklung im Container (Dauer: ~4 Tage)

**Ziel:** Einen robusten Backend-Service entwickeln, der die Workout-Daten empfängt, verarbeitet und in Google Sheets einträgt.

1.  **`requirements.txt` erstellen:**
    ```
    Flask==2.2.2
    gspread==5.7.2
    oauth2client==4.1.3
    pandas==1.5.3
    ```

2.  **`Dockerfile` für das Backend:**
    ```Dockerfile
    FROM python:3.9-slim

    WORKDIR /app

    COPY requirements.txt .

    RUN pip install --no-cache-dir -r requirements.txt

    COPY . .

    CMD ["python", "app.py"]
    ```

3.  **Logik in `app.py` implementieren:**
    *   **Flask-Server aufsetzen:** Erstelle eine einfache Flask-Anwendung.
    *   **API-Endpunkt `/upload`:**
        *   Implementiere eine `POST`-Route, die eine CSV-Datei entgegennimmt.
        *   Lese die CSV-Daten mit `pandas`.
        *   Verarbeite die Daten: Bereinige Spalten, formatiere Daten und berechne bei Bedarf zusätzliche Metriken.
    *   **Google Sheets-Integration:**
        *   Authentifiziere dich mit `gspread` und den Anmeldeinformationen aus der `service-account.json`.
        *   Öffne das Ziel-Spreadsheet und das entsprechende Arbeitsblatt.
        *   Schreibe die verarbeiteten Daten in das Arbeitsblatt.
    *   **Fehlerbehandlung:** Implementiere eine robuste Fehlerbehandlung für den Fall, dass die Datei nicht korrekt formatiert ist oder die Google API nicht erreichbar ist.

## Phase 3: Frontend-Entwicklung im Container (Dauer: ~3 Tage)


**Ziel:** Eine benutzerfreundliche Oberfläche schaffen, über die der Benutzer seine Workout-Daten hochladen kann.

1.  **`Dockerfile` für das Frontend:**
    ```Dockerfile
    FROM nginx:stable-alpine

    COPY ./ /usr/share/nginx/html

    EXPOSE 80
    ```

2.  **`index.html` erstellen:**
    *   Erstelle ein einfaches HTML-Formular mit einem Datei-Upload-Feld (`<input type="file">`) und einem Senden-Button.
    *   Stelle sicher, dass das Formular nur `.csv`-Dateien akzeptiert.

3.  **JavaScript für den Upload:**
    *   Schreibe eine JavaScript-Funktion, die die ausgewählte Datei erfasst.
    *   Verwende die `fetch`-API, um die Datei an den Backend-Endpunkt `http://localhost:5000/upload` zu senden.
    *   Zeige dem Benutzer eine Erfolgs- oder Fehlermeldung an, je nach Antwort des Backends.
    *   Da beide Services im selben Docker-Netzwerk laufen, kann das Frontend den Backend-Service über seinen Namen (`backend`) ansprechen: `fetch('http://backend:5000/upload', ...)`

## Phase 4: Test und Deployment (Dauer: ~1 Tag)

**Ziel:** Die Anwendung gründlich testen und für das Deployment vorbereiten.

1.  **`docker-compose.yml` finalisieren:**
    ```yaml
    version: '3.8'
    services:
      backend:
        build: ./backend
        ports:
          - "5000:5000"
        volumes:
          - ./service-account.json:/app/service-account.json:ro
      frontend:
        build: ./frontend
        ports:
          - "8080:80"
        depends_on:
          - backend
    ```

2.  **Lokales Deployment:**
    *   Starte die gesamte Anwendung mit `docker-compose up --build`.
    *   Docker Compose baut die Images und startet die Container in der richtigen Reihenfolge.

3.  **Fehlerbehebung:**
    *   Überprüfe die Logs beider Container mit `docker-compose logs -f backend` und `docker-compose logs -f frontend`.
    *   Behebe eventuelle Fehler in der Kommunikation oder bei den API-Aufrufen.

4.  **Deployment auf einem Server:**
    *   Klone das GitHub-Repository auf deinen Server.
    *   Führe `docker-compose up -d` aus, um die Anwendung im Hintergrund zu starten.

## Phase 5: Wartung und zukünftige Features

**Ziel:** Die Anwendung langfristig pflegen und erweitern.

*   **Regelmäßige Updates:** Halte die Abhängigkeiten (Python-Bibliotheken, Docker-Images) auf dem neuesten Stand.
*   **Monitoring:** Überwache die Anwendung auf Fehler und Performance-Probleme.
*   **Zukünftige Features:**
    *   **Datenvisualisierung:** Füge Diagramme und Grafiken hinzu, um die Workout-Daten direkt im Frontend zu visualisieren.
    *   **Benutzer-Feedback:** Implementiere eine Möglichkeit für Benutzer, Feedback zu geben oder Fehler zu melden.
    *   **Unterstützung für weitere Datenquellen:** Erweitere die Anwendung, um Daten aus anderen Fitness-Apps oder Geräten zu importieren.
