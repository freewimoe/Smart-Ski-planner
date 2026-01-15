import pandas as pd
import numpy as np
import json
from pathlib import Path
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import wikipedia

# Path to resorts JSON file
RESORTS_FILE = Path(__file__).parent / "resorts.json"


def get_ski_resorts(include_full_data: bool = False) -> pd.DataFrame:
    """
    Load resort data from JSON file.

    Args:
        include_full_data: If True, return all fields including nested data.
                          If False, return only basic fields for compatibility.
    """
    try:
        with open(RESORTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        resorts = data.get('resorts', [])

        if not include_full_data:
            # Return only basic fields for backward compatibility
            basic_resorts = []
            for r in resorts:
                basic_resorts.append({
                    'name': r['name'],
                    'lat': r['lat'],
                    'lon': r['lon'],
                    'altitude_m': r['altitude_m'],
                    'country': r['country'],
                    'slopes_km': r['slopes_km'],
                    'lifts': r['lifts']
                })
            return pd.DataFrame(basic_resorts)

        return pd.DataFrame(resorts)

    except FileNotFoundError:
        # Fallback to hardcoded data if JSON not found
        return _get_fallback_resorts()


def get_resort_details(resort_name: str) -> dict:
    """
    Get full details for a specific resort.

    Args:
        resort_name: Name of the resort

    Returns:
        Dict with all resort data or None if not found
    """
    try:
        with open(RESORTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for resort in data.get('resorts', []):
            if resort['name'] == resort_name:
                return resort
        return None

    except FileNotFoundError:
        return None


def get_all_resort_details() -> dict:
    """
    Get full details for all resorts as a dict keyed by name.
    """
    try:
        with open(RESORTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return {r['name']: r for r in data.get('resorts', [])}

    except FileNotFoundError:
        return {}


def _get_fallback_resorts() -> pd.DataFrame:
    """Fallback resort data if JSON file is missing."""
    resorts = [
        {"name": "Garmisch-Partenkirchen", "lat": 47.4917, "lon": 11.0955,
         "altitude_m": 708, "country": "Germany", "slopes_km": 40, "lifts": 17},
        {"name": "Kitzbuehel", "lat": 47.4464, "lon": 12.3909,
         "altitude_m": 762, "country": "Austria", "slopes_km": 233, "lifts": 57},
        {"name": "St. Anton am Arlberg", "lat": 47.1296, "lon": 10.2682,
         "altitude_m": 1304, "country": "Austria", "slopes_km": 305, "lifts": 88},
        {"name": "Ischgl", "lat": 47.0112, "lon": 10.2905,
         "altitude_m": 1377, "country": "Austria", "slopes_km": 239, "lifts": 45},
        {"name": "Winterberg", "lat": 51.1965, "lon": 8.5258,
         "altitude_m": 668, "country": "Germany", "slopes_km": 27.5, "lifts": 24},
        {"name": "Feldberg", "lat": 47.8596, "lon": 8.0039,
         "altitude_m": 950, "country": "Germany", "slopes_km": 63, "lifts": 38},
        {"name": "Zermatt", "lat": 46.0207, "lon": 7.7491,
         "altitude_m": 1608, "country": "Switzerland", "slopes_km": 360, "lifts": 52},
        {"name": "Davos", "lat": 46.8027, "lon": 9.8287,
         "altitude_m": 1560, "country": "Switzerland", "slopes_km": 269, "lifts": 57},
        {"name": "Chamonix", "lat": 45.9237, "lon": 6.8694,
         "altitude_m": 1035, "country": "France", "slopes_km": 119, "lifts": 67},
    ]
    return pd.DataFrame(resorts)

def get_wiki_summary(place_name):
    """
    Fetches a short summary from Wikipedia.
    """
    try:
        # Set language based on country could be cool, but let's stick to English or German.
        # wikipedia.set_lang("de") # Uncomment for German
        summary = wikipedia.summary(place_name + " ski resort", sentences=3)
        return summary
    except wikipedia.exceptions.PageError:
        try:
            return wikipedia.summary(place_name, sentences=3)
        except:
            return "No description available on Wikipedia."
    except Exception:
         return "Could not fetch description."

def geocode_address(street, number, zip_code, city, country="Germany"):
    """
    Converts an address to (lat, lon) using OpenStreetMap's Nominatim.
    """
    geolocator = Nominatim(user_agent="smart_ski_planner_2026_demo")
    address_str = f"{street} {number}, {zip_code} {city}, {country}"
    
    try:
        location = geolocator.geocode(address_str, timeout=10)
        if location:
            return location.latitude, location.longitude
        else:
            return None
    except GeocoderTimedOut:
        return None

def calculate_distance(start_coords, end_coords):
    """
    Calculate distance in km between two (lat, lon) tuples.
    """
    return geodesic(start_coords, end_coords).km

def filter_resorts_by_distance(resorts_df, user_lat, user_lon, max_km):
    user_location = (user_lat, user_lon)
    
    # Calculate distance for each resort
    resorts_df['distance_km'] = resorts_df.apply(
        lambda row: calculate_distance(user_location, (row['lat'], row['lon'])), axis=1
    )
    
    return resorts_df[resorts_df['distance_km'] <= max_km].copy()

def generate_hotel_options(resort_name, adults, children, rooms):
    """
    Generates dummy hotel data for a given resort.
    """
    np.random.seed(len(resort_name)) # Deterministic per resort
    hotels = []
    for i in range(1, 6):
        base_price = np.random.randint(1500, 5000)
        # Price adjustment based on rooms and people
        total_people = adults + children
        price = base_price + (rooms * 200) + (total_people * 100)
        
        # Placeholder for Real Booking Link
        search_url = f"https://www.booking.com/searchresults.html?ss={resort_name.replace(' ', '+')}"
        
        hotels.append({
            "hotel_name": f"Hotel {resort_name} {i}",
            "stars": np.random.randint(3, 6),
            "price_total": price,
            "rooms_available": rooms,
            "family_friendly": True if np.random.rand() > 0.3 else False,
            "booking_url": search_url
        })
    return pd.DataFrame(hotels)
