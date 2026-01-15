# ⛷️ Smart Ski Vacation Planner

Dein intelligenter Begleiter für den perfekten Skiurlaub im Februar 2026. Dieses Tool verbindet Machine Learning, Live-Daten und Geo-Services, um die beste Destination für dich und deine Familie zu finden.

## 🎯 Use Cases & Features

### 1. Smarte Destinations-Findung 🧠
*   **Problem**: "Wo liegt im Februar 2026 sicher Schnee, ohne dass ich 1000km fahren muss?"
*   **Lösung**: 
    *   **ML-Schneeprognose**: Ein Random Forest Modell sagt die Schneehöhe basierend auf historischen Daten vorher.
    *   **Real-Data Training**: Das Modell kann optional live mit echten Wetterdaten der letzten 3 Jahre (Open-Meteo API) trainiert werden.
    *   **Distanz-Filter**: Finde Resorts in deinem bevorzugten Radius (z.B. max 400km).

### 2. Interaktive Reiseplanung 🗺️
*   **Problem**: "Wie weit ist es von meiner Haustür?"
*   **Lösung**:
    *   **Adresseingabe**: Gib deine Straße und Stadt ein – das Tool findet deinen Standort exakt (Geocoding).
    *   **Visuelle Routen**: Eine interaktive Karte zeigt dir per Luftlinie deine Optionen und die relative Lage der Skigebiete.

### 3. Deep-Dive Resort Insights 🏔️
*   **Problem**: "Ist das Skigebiet gut? Wie ist das Wetter gerade?"
*   **Lösung**:
    *   **Live Wetter & Forecast**: Aktuelle Temperatur, Wind und 7-Tage-Vorschau (Open-Meteo).
    *   **Windy.com Integration**: Interaktive Wetterkarte mit Wind- und Schneeradar direkt im Tool.
    *   **Wikipedia-Infos**: Automatisch geladene Kurzbeschreibungen und Fakten zum Ort.

### 4. Unterkunft & Familie 🏨
*   **Problem**: "Wir brauchen 3 Schlafzimmer für 2 Erwachsene und 2 Kinder."
*   **Lösung**: 
    *   **Maßgeschneiderte Suche**: Generiert Hotelvorschläge basierend auf deiner Personenanzahl.
    *   **Direkt-Buchung**: Smart-Links führen dich direkt zu den Suchergebnissen auf Booking.com für deinen Zeitraum.

### 5. Personalisiertes Erlebnis 👤
*   **Problem**: "Ich möchte meine Favoriten speichern."
*   **Lösung**:
    *   **User Accounts**: Sicheres Login & Registrierung (passwort-verschlüsselt via `bcrypt`).
    *   **Trip-Speicher**: Merke dir spannende Resorts in deiner persönlichen Liste (SQLite Datenbank).

---

## 🛠️ Tech Stack
*   **Frontend**: Streamlit
*   **Machine Learning**: Scikit-Learn (Random Forest)
*   **Geo-Services**: Folium, OpenStreetMap Nominatim, Open-Meteo API
*   **Data**: Pandas, Wikipedia API, Windy.com Embed
*   **Backend/DB**: SQLite, Bcrypt

## 🚀 Installation & Start

1. **Python installieren** (falls nicht vorhanden).
2. **Abhängigkeiten installieren**:
   ```bash
   pip install -r requirements.txt
   ```
3. **App starten**:
   ```bash
   streamlit run app.py
   ```
   Das Tool öffnet sich automatisch im Browser unter `http://localhost:8501`.

## ☁️ Deployment

Dieses Projekt ist "**Cloud Ready**" für **Streamlit Cloud**.

1. **Git Repository pushen**:
   ```bash
   git init
   git add .
   git commit -m "Ready for deploy"
   git push origin main
   ```
2. **Auf [Streamlit Share](https://share.streamlit.io) deployen**:
   - Repository auswählen -> Deploy klicken.
   - Das Modell trainiert sich beim ersten Start in der Cloud automatisch neu.
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
