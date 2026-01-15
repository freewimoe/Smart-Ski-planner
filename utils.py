import pandas as pd
import numpy as np
from geopy.distance import geodesic

# Mock Data for Ski Resorts
def get_ski_resorts():
    # Coordinates are approximate
    resorts = [
        {"name": "Garmisch-Partenkirchen", "lat": 47.4917, "lon": 11.0955, "altitude_m": 708, "country": "Germany"},
        {"name": "Kitzbühel", "lat": 47.4464, "lon": 12.3909, "altitude_m": 762, "country": "Austria"},
        {"name": "St. Anton am Arlberg", "lat": 47.1296, "lon": 10.2682, "altitude_m": 1304, "country": "Austria"},
        {"name": "Ischgl", "lat": 47.0112, "lon": 10.2905, "altitude_m": 1377, "country": "Austria"},
        {"name": "Winterberg", "lat": 51.1965, "lon": 8.5258, "altitude_m": 668, "country": "Germany"},
        {"name": "Feldberg", "lat": 47.8596, "lon": 8.0039, "altitude_m": 950, "country": "Germany"},
        {"name": "Zermatt", "lat": 46.0207, "lon": 7.7491, "altitude_m": 1608, "country": "Switzerland"},
        {"name": "Davos", "lat": 46.8027, "lon": 9.8287, "altitude_m": 1560, "country": "Switzerland"},
        {"name": "Chamonix", "lat": 45.9237, "lon": 6.8694, "altitude_m": 1035, "country": "France"},
    ]
    return pd.DataFrame(resorts)

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
