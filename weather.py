import requests
import pandas as pd

def get_live_weather(lat, lon):
    """
    Fetches current weather and 7-day forecast from Open-Meteo.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ["temperature_2m", "wind_speed_10m", "snow_depth"],
        "daily": ["temperature_2m_max", "temperature_2m_min", "snowfall_sum", "precipitation_probability_max"],
        "timezone": "auto"
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Current Data
        current = {
            "temp": data['current']['temperature_2m'],
            "wind": data['current']['wind_speed_10m'],
            "snow_depth": data['current'].get('snow_depth', 0)
        }
        
        # Forecast DataFrame
        daily = data['daily']
        df_forecast = pd.DataFrame({
            "Date": daily['time'],
            "Max Temp (°C)": daily['temperature_2m_max'],
            "Min Temp (°C)": daily['temperature_2m_min'],
            "Snowfall (cm)": daily['snowfall_sum'],
            "Precip Prob (%)": daily['precipitation_probability_max']
        })
        
        return current, df_forecast
        
    except Exception as e:
        print(f"Weather API Error: {e}")
        return None, None
