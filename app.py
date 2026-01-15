import streamlit as st
import pandas as pd
import datetime
import folium
import streamlit.components.v1 as components
from streamlit_folium import st_folium
from utils import get_ski_resorts, filter_resorts_by_distance, generate_hotel_options, geocode_address, get_wiki_summary
from model import load_or_train_model, predict_snow_quality
from db import init_db, login_user, register_user, save_trip, get_user_trips
from weather import get_live_weather

# Initialize DB
init_db()

st.set_page_config(page_title="Smart Ski Vacation Planner", page_icon="⛷️", layout="wide")

# Session State Init
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None

# --- AUTHENTICATION ---
if not st.session_state['user_id']:
    st.title("⛷️ Willkommen beim Ski-Planner")
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        l_user = st.text_input("Username", key="l_user")
        l_pass = st.text_input("Password", type="password", key="l_pass")
        if st.button("Login"):
            uid = login_user(l_user, l_pass)
            if uid:
                st.session_state['user_id'] = uid
                st.session_state['username'] = l_user
                st.rerun()
            else:
                st.error("Invalid credentials")
                
    with tab2:
        r_user = st.text_input("New Username", key="r_user")
        r_pass = st.text_input("New Password", type="password", key="r_pass")
        if st.button("Register"):
            if register_user(r_user, r_pass):
                st.success("Account created! Please login.")
            else:
                st.error("Username already taken.")
    
    st.stop() # Stop execution here if not logged in

# --- MAIN APP (LOGGED IN) ---

st.sidebar.write(f"Logged in as: **{st.session_state['username']}**")
if st.sidebar.button("Logout"):
    st.session_state['user_id'] = None
    st.rerun()

# Title and Description
st.title("⛷️ Smart Ski Vacation Planner 2026")
st.markdown("""
This ML-powered tool helps you find the perfect ski vacation.
Select your location by clicking on the map or entering coordinates.
""")

# Sidebar for Inputs
st.sidebar.header("Travel Parameters")

# Location Setup - NOW INTERACTIVE
st.sidebar.subheader("Your Location")

# Default Location (Frankfurt)
default_lat = 50.1109
default_lon = 8.6821

# Initialize map location in session state if not set
if 'map_lat' not in st.session_state:
    st.session_state['map_lat'] = default_lat
if 'map_lon' not in st.session_state:
    st.session_state['map_lon'] = default_lon

# 1. Map for Location Selection
st.subheader("1. Select Your Start Location")

# Address Search Form
with st.expander("📍 Search by Address", expanded=True):
    c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
    street = c1.text_input("Street", placeholder="Main St")
    number = c2.text_input("No", placeholder="1")
    zip_code = c3.text_input("Zip", placeholder="10115")
    city = c4.text_input("City", placeholder="Berlin")
    
    if st.button("Find Address"):
        if street and city:
            coords = geocode_address(street, number, zip_code, city)
            if coords:
                st.session_state['map_lat'] = coords[0]
                st.session_state['map_lon'] = coords[1]
                st.success(f"Found: {street} {number}, {city} ({coords[0]:.4f}, {coords[1]:.4f})")
                st.rerun()
            else:
                st.error("Address not found.")
        else:
            st.warning("Please enter at least Street and City.")

st.info("Or click on the map / drag the map to adjust.")

m_start = folium.Map(location=[st.session_state['map_lat'], st.session_state['map_lon']], zoom_start=9)
folium.Marker(
    [st.session_state['map_lat'], st.session_state['map_lon']], 
    popup="Your Start", 
    tooltip="Your Location",
    icon=folium.Icon(color="red", icon="home")
).add_to(m_start)

# Capture Map Click
output = st_folium(m_start, height=300, width="100%", key="starter_map")

if output['last_clicked']:
    st.session_state['map_lat'] = output['last_clicked']['lat']
    st.session_state['map_lon'] = output['last_clicked']['lng']
    st.rerun() # Refresh to update calculations

user_lat = st.session_state['map_lat']
user_lon = st.session_state['map_lon']

st.write(f"Selected Location: **{user_lat:.4f}, {user_lon:.4f}**")

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

# --- Results Logic ---

st.subheader("2. Found Resorts & Routes")
filtered_resorts = filter_resorts_by_distance(resorts_df, user_lat, user_lon, max_dist)

if filtered_resorts.empty:
    st.warning("No resorts found within that distance. Try increasing the range!")
else:
    # Predict Snow
    filtered_resorts['predicted_snow_cm'] = filtered_resorts.apply(
        lambda row: predict_snow_quality(snow_model, travel_month, row['altitude_m'], row['lat']), axis=1
    )
    
    # Sort by snow
    filtered_resorts = filtered_resorts.sort_values(by='predicted_snow_cm', ascending=False)

    # --- RESULTS MAP ---
    # Create a map centered between user and first result
    mid_lat = (user_lat + filtered_resorts.iloc[0]['lat']) / 2
    mid_lon = (user_lon + filtered_resorts.iloc[0]['lon']) / 2
    
    m_results = folium.Map(location=[mid_lat, mid_lon], zoom_start=6)
    
    # User Marker
    folium.Marker(
        [user_lat, user_lon], 
        popup="Your Start", 
        icon=folium.Icon(color="red", icon="home")
    ).add_to(m_results)
    
    # Add Resorts and Lines
    for idx, row in filtered_resorts.iterrows():
        # Resort Marker
        folium.Marker(
            [row['lat'], row['lon']],
            popup=f"<b>{row['name']}</b><br>Snow: {row['predicted_snow_cm']}cm",
            tooltip=row['name'],
            icon=folium.Icon(color="blue", icon="snowflake", prefix="fa")
        ).add_to(m_results)
        
        # Line from User to Resort
        folium.PolyLine(
            locations=[(user_lat, user_lon), (row['lat'], row['lon'])],
            color="blue",
            weight=2,
            opacity=0.5,
            dash_array='5, 10'
        ).add_to(m_results)

    # Display Map
    st_folium(m_results, height=400, width="100%", key="results_map")
    
    # --- RESULT TABLE with Selection ---
    st.write("### Usage: Select a row to update hotels")
    
    # Using new st.dataframe selection (Streamlit 1.35+)
    selection = st.dataframe(
        filtered_resorts[['name', 'country', 'distance_km', 'altitude_m', 'slopes_km', 'predicted_snow_cm']],
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    selected_row_index = selection.selection.rows
    
    selected_resort_name = None
    selected_resort_data = None
    
    if selected_row_index:
        selected_resort_data = filtered_resorts.iloc[selected_row_index[0]]
        selected_resort_name = selected_resort_data['name']
    
    # 3. Details & Hotels
    if selected_resort_name:
        st.subheader(f"3. Details for: {selected_resort_name}")
        
        # Save Trip Button (Persistence)
        col_save, col_info = st.columns([1, 4])
        with col_save:
            if st.button("💾 Save this Trip"):
                save_trip(st.session_state['user_id'], user_lat, user_lon, selected_resort_name, start_date)
                st.toast(f"Trip to {selected_resort_name} saved!")
        
        # Tabs for different Info Categories
        tab_hotels, tab_weather, tab_info, tab_map = st.tabs(["🏨 Hotels", "🌤️ Live Weather", "ℹ️ Resort Info", "🗺️ Windy Map"])
        
        with tab_hotels:
            hotels_df = generate_hotel_options(selected_resort_name, adults, children, rooms)
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
        
        with tab_weather:
            st.markdown("### Current Weather & 7-Day Forecast")
            lat = selected_resort_data['lat']
            lon = selected_resort_data['lon']
            
            with st.spinner("Fetching live weather..."):
                current_w, df_forecast = get_live_weather(lat, lon)
            
            if current_w:
                w1, w2, w3 = st.columns(3)
                w1.metric("Temperature", f"{current_w['temp']} °C")
                w2.metric("Wind Speed", f"{current_w['wind']} km/h")
                w3.metric("Current Snow Depth", f"{current_w['snow_depth'] * 100:.1f} cm") # m to cm
                
                st.write("#### 7-Day Forecast")
                st.dataframe(df_forecast, use_container_width=True)
            else:
                st.error("Could not fetch weather data.")
                
        with tab_info:
            st.markdown(f"### About {selected_resort_name}")
            with st.spinner("Fetching Wikipedia summary..."):
                wiki_text = get_wiki_summary(selected_resort_name)
            st.info(wiki_text)
            
            st.markdown("### Stats")
            st.write(f"**Altitude:** {selected_resort_data['altitude_m']} m")
            st.write(f"**Slopes:** {selected_resort_data.get('slopes_km', 'N/A')} km")
            st.write(f"**Lifts:** {selected_resort_data.get('lifts', 'N/A')}")
            
        with tab_map:
            st.markdown("### Live Wind & Weather Map (Windy.com)")
            # Embedding Windy.com iframe
            windy_url = f"https://embed.windy.com/embed2.html?lat={lat}&lon={lon}&detailLat={lat}&detailLon={lon}&width=650&height=450&zoom=11&level=surface&overlay=wind&product=ecmwf&menu=&message=&marker=&calendar=now&pressure=&type=map&location=coordinates&detail=&metricWind=default&metricTemp=default&radarRange=-1"
            components.iframe(windy_url, height=500)

# Show saved trips in Sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("My Saved Trips")
user_trips = get_user_trips(st.session_state['user_id'])
if user_trips:
    for trip in user_trips:
        st.sidebar.text(f"📍 {trip[0]}\n📅 {trip[1]}")
else:
    st.sidebar.text("No saved trips yet.")


