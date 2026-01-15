import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import pickle
import os
import requests
import time

MODEL_FILE_SYNTHETIC = 'snow_model_synthetic.pkl'
MODEL_FILE_REAL = 'snow_model_real.pkl'

def fetch_historical_snow_data(lat, lon, years_back=3):
    """
    Fetches historical snow data from Open-Meteo Archive API.
    """
    print(f"Fetching data for {lat}, {lon}...")
    end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
    start_date = (pd.Timestamp.now() - pd.DateOffset(years=years_back)).strftime('%Y-%m-%d')
    
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": "2023-12-31", # Use a fixed end date for consistent history or dynamic
        "daily": ["snow_depth_max", "temperature_2m_mean"],
        "timezone": "Europe/Berlin"
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'daily' not in data:
            return pd.DataFrame()
            
        df = pd.DataFrame({
            'date': data['daily']['time'],
            'snow_depth_cm': [s * 100 if s else 0 for s in data['daily']['snow_depth_max']], # m to cm
            'temp_mean': data['daily']['temperature_2m_mean']
        })
        df['date'] = pd.to_datetime(df['date'])
        df['month'] = df['date'].dt.month
        df['latitude'] = lat
        
        # Add altitude if available or pass it in. For model simplicity we might skip altitude in fetch 
        # or assume correlation. Ideally we need altitude of the station.
        # Open-Meteo returns elevation in metadata
        elevation = data.get('elevation', 500)
        df['altitude'] = elevation
        
        return df
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

def generate_training_data(use_real_data=False):
    """
    Generates data. If use_real_data is True, fetches from Open-Meteo.
    Otherwise uses synthetic logic.
    """
    if not use_real_data:
        # ... existing synthetic logic ...
        n_samples = 1000
        data = []
        for _ in range(n_samples):
            month = np.random.randint(1, 13)
            altitude = np.random.randint(500, 3000)
            latitude = np.random.uniform(45.0, 52.0)
            base_snow = 0
            if month in [12, 1, 2, 3]:
                base_snow = 50 + (altitude / 20) + ((latitude - 45) * 10)
            elif month in [11, 4]:
                base_snow = 20 + (altitude / 30)
            else:
                base_snow = 0 + (altitude / 100) 
            noise = np.random.normal(0, 10)
            snow_depth = max(0, base_snow + noise)
            data.append([month, altitude, latitude, snow_depth])
        return pd.DataFrame(data, columns=['month', 'altitude', 'latitude', 'snow_depth_cm'])

    # Real Data Strategy:
    # Fetch data for a few key ski locations to represent the distribution
    sample_locs = [
        (47.4917, 11.0955), # Garmisch
        (46.0207, 7.7491),  # Zermatt
        (51.1965, 8.5258),  # Winterberg
        (45.9237, 6.8694)   # Chamonix
    ]
    
    all_data = []
    for lat, lon in sample_locs:
        df = fetch_historical_snow_data(lat, lon)
        if not df.empty:
            # Drop NaN
            df = df.dropna()
            # Select relevant columns
            all_data.append(df[['month', 'altitude', 'latitude', 'snow_depth_cm']])
        time.sleep(1) # Respect API rate limits
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        print("Fallback to synthetic data due to API failure.")
        return generate_training_data(use_real_data=False)

def train_and_save_model(use_real_data=False):
    """
    Trains a Random Forest model and saves it.
    """
    print(f"Training Snow Prediction Model (Real Data: {use_real_data})...")
    df = generate_training_data(use_real_data=use_real_data)
    
    if df.empty:
        print("No data collected.")
        return None
        
    X = df[['month', 'altitude', 'latitude']]
    y = df['snow_depth_cm']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    score = model.score(X_test, y_test)
    print(f"Model R2 Score: {score:.2f}")
    
    model_file = MODEL_FILE_REAL if use_real_data else MODEL_FILE_SYNTHETIC
    with open(model_file, 'wb') as f:
        pickle.dump(model, f)
        
    return model

def load_or_train_model(force_retrain=False, use_real_data=False):
    model_file = MODEL_FILE_REAL if use_real_data else MODEL_FILE_SYNTHETIC
    
    if not force_retrain and os.path.exists(model_file):
        with open(model_file, 'rb') as f:
            return pickle.load(f)
    else:
        return train_and_save_model(use_real_data=use_real_data)

def predict_snow_quality(model, month, altitude, latitude):
    prediction = model.predict([[month, altitude, latitude]])[0]
    return max(0, round(prediction, 1))
