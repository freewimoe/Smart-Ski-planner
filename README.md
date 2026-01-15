# Smart Ski Vacation Planner

Ein "Smart Tool" zur Planung des Skiurlaubs 2026.

## Features
- **Interactive Map Input**: Wähle deinen Startpunkt per Klick auf die Karte (OpenStreetMap/Folium).
- **User Login & Persistence**: 
  - Login/Register System.
  - Speichert gesuchte Urlaubsziele in einer SQLite Datenbank.
- **Visual Routes**: Zeigt Linien von deinem Startpunkt zu allen möglichen Resorts.
- **Distanz-Check**: Findet Skigebiete im Umkreis von X km.
- **ML Snow Prediction**: 
  - Standard: Trainiert auf synthetischen Daten.
  - **NEU: Real Data Mode**: Kann **Open-Meteo Archive API** nutzen, um auf echten historischen Schneedaten der letzten 3 Jahre zu trainieren!
- **Hotel Empfehlung**: Generiert Optionen und verlinkt auf **Booking.com** Suche für den jeweiligen Ort.


## Installation

1. Python installieren.
2. Umgebung erstellen (optional):
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate
   ```
3. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```

## Starten

```bash
streamlit run app.py
```

Das Tool öffnet sich automatisch im Browser.

## Deployment (Git & Streamlit Cloud)

Dieses Projekt ist "**Cloud Ready**". Um es online zu stellen:

1. **Git Repository erstellen**:
   ```bash
   git init
   git add .
   git commit -m "Initial Smart Ski Planner"
   ```
2. **Auf GitHub pushen**.
3. **Auf Streamlit Community Cloud anmelden**:
   - Verbinde deinen GitHub Account.
   - Wähle das Repository aus.
   - Klicke auf "Deploy".
   
Das Modell wird beim ersten Start in der Cloud automatisch trainiert (Synthetisch). Wenn "Real Data" gewählt wird, lädt es die Daten live nach.
