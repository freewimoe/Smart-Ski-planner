import streamlit as st
import pandas as pd
import datetime
from utils import get_ski_resorts, filter_resorts_by_distance, generate_hotel_options
from model import load_or_train_model, predict_snow_quality

st.set_page_config(page_title="Smart Ski Vacation Planner", page_icon="⛷️", layout="wide")

# Title and Description
st.title("⛷️ Smart Ski Vacation Planner 2026")
st.markdown("""
This ML-powered tool helps you find the perfect ski vacation.
It finds resorts within your range, predicts snow quality using Machine Learning, and suggests hotels.
""")

# Sidebar for Inputs
st.sidebar.header("Travel Parameters")

# Location Setup
st.sidebar.subheader("Your Location")
# Defaults to roughly Frankfurt/Main for demo
user_lat = st.sidebar.number_input("Latitude", value=50.1109, format="%.4f")
user_lon = st.sidebar.number_input("Longitude", value=8.6821, format="%.4f")
max_dist = st.sidebar.slider("Max Distance (km)", 100, 1000, 400)

# Trip Dates
st.sidebar.subheader("Dates")
default_start = datetime.date(2026, 2, 14)
default_end = datetime.date(2026, 2, 21)
trip_dates = st.sidebar.date_input("Travel Dates", [default_start, default_end])

# Party Details
st.sidebar.subheader("Party Details")
col1, col2 = st.sidebar.columns(2)
with col1:
    adults = st.number_input("Adults", min_value=1, value=2)
    rooms = st.number_input("Bedrooms", min_value=1, value=3)
with col2:
    children = st.number_input("Children", min_value=0, value=2)
    child_age = st.number_input("Child Age", min_value=0, value=12)

# Load Data and Model
resorts_df = get_ski_resorts()

@st.cache_resource
def get_cached_model(use_real_data):
    """
    Wrapper to cache the model in memory so we don't retrain on every reload.
    """
    return load_or_train_model(use_real_data=use_real_data)

# Option to Retrain with Real Data
with st.sidebar.expander("Admin / Model Settings"):
    use_real_data = st.checkbox("Use Real Historical Weather API (Open-Meteo)", value=False)
    if st.button("Retrain Snow Model"):
        with st.spinner("Retraining model (may take 10-20s if API enabled)..."):
            get_cached_model.clear() # Clear cache to force new training
            snow_model = get_cached_model(use_real_data)
        st.success("Model retrained successfully!")

# Load model (cached)
snow_model = get_cached_model(use_real_data)

# Process Trip Month for Prediction
start_date = trip_dates[0] if isinstance(trip_dates, list) and len(trip_dates) > 0 else default_start
travel_month = start_date.month

# --- Main App Logic ---

# 1. Filter by Distance
st.subheader("1. Finding Resorts Nearby")
filtered_resorts = filter_resorts_by_distance(resorts_df, user_lat, user_lon, max_dist)

if filtered_resorts.empty:
    st.warning("No resorts found within that distance. Try increasing the range!")
else:
    st.success(f"Found {len(filtered_resorts)} resorts within {max_dist} km.")
    
    # 2. Predict Snow Quality
    st.subheader("2. ML Snow Prediction")
    
    # Apply ML Model
    filtered_resorts['predicted_snow_cm'] = filtered_resorts.apply(
        lambda row: predict_snow_quality(snow_model, travel_month, row['altitude_m'], row['lat']), axis=1
    )
    
    # Display Map
    st.map(filtered_resorts[['lat', 'lon']])
    
    # Display Table with Snow Prediction
    st.dataframe(
        filtered_resorts[['name', 'country', 'distance_km', 'altitude_m', 'predicted_snow_cm']]
        .sort_values(by='predicted_snow_cm', ascending=False)
        .style.format({"distance_km": "{:.1f}", "predicted_snow_cm": "{:.1f} cm"})
    )
    
    # 3. Hotel Finder
    st.subheader("3. Hotel Recommendations")
    selected_resort = st.selectbox("Select a Resort to view hotels:", filtered_resorts['name'])
    
    if selected_resort:
        st.write(f"Searching available hotels in **{selected_resort}** for {adults} Adults, {children} Children ({child_age}y) in {rooms} rooms...")
        
        hotels_df = generate_hotel_options(selected_resort, adults, children, rooms)
        
        # Display Hotels
        for i, hotel in hotels_df.iterrows():
            with st.expander(f"{hotel['hotel_name']} - €{hotel['price_total']}"):
                col_h1, col_h2 = st.columns([3, 1])
                with col_h1:
                    st.write(f"**Stars:** {'⭐' * int(hotel['stars'])}")
                    st.write(f"**Family Friendly:** {'✅' if hotel['family_friendly'] else '❌'}")
                    st.write(f"**Available Rooms:** {hotel['rooms_available']}")
                with col_h2:
                    st.link_button("Check Booking.com", hotel['booking_url'])
                    st.button("Mock Book", key=f"btn_{i}")

