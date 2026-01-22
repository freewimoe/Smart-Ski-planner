"""
Smart Ski Vacation Planner 2026 - Level 2.5
Enhanced with real snow conditions, accommodation pricing, and advanced comparison.
"""

import streamlit as st
import pandas as pd
import datetime
from datetime import date, timedelta
import folium
import streamlit.components.v1 as components
from streamlit_folium import st_folium

# Core imports
from utils import (
    get_ski_resorts, filter_resorts_by_distance, generate_hotel_options,
    geocode_address, get_wiki_summary, get_all_resort_details
)
from model import load_or_train_model, predict_snow_quality
from db import (
    init_db, login_user, register_user, save_trip, get_user_trips,
    get_user_preferences, save_user_preferences, get_default_preferences,
    add_favorite, remove_favorite, is_favorite, get_user_favorites,
    get_resort_reviews, get_resort_rating_summary, submit_review
)
from weather import get_live_weather, get_enhanced_snow_data, format_snow_display

# Level 2 imports
from preferences import UserPreferences, ResortMatcher
from budget import (
    TravelParty, TripDetails, BudgetOptions,
    TransportMode, get_budget_summary
)
from compare import ResortComparator, create_comprehensive_comparison

# Level 2.5 imports - Snow and Accommodation
try:
    from snow_api import SnowConditionAggregator
    from snow_conditions import get_avalanche_risk_label, get_avalanche_risk_color
    SNOW_API_AVAILABLE = True
except ImportError:
    SNOW_API_AVAILABLE = False

try:
    from accommodation import AccommodationSearch, TravelGroup, get_accommodation_url
    ACCOMMODATION_AVAILABLE = True
except ImportError:
    ACCOMMODATION_AVAILABLE = False

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

    st.stop()

# --- MAIN APP (LOGGED IN) ---

st.sidebar.write(f"Logged in as: **{st.session_state['username']}**")
if st.sidebar.button("Logout"):
    st.session_state['user_id'] = None
    st.rerun()

# Title and Description
st.title("⛷️ Smart Ski Vacation Planner 2026")
st.markdown("""
This ML-powered tool helps you find the perfect ski vacation.
Select your location, set your preferences, and compare resorts!
""")

# Sidebar for Inputs
st.sidebar.header("Travel Parameters")

# =============================================================================
# USER PREFERENCES (Level 2 - NEW)
# =============================================================================

# Load user preferences
user_prefs_data = get_user_preferences(st.session_state['user_id'])
if not user_prefs_data:
    user_prefs_data = get_default_preferences()

with st.sidebar.expander("🎯 Meine Praeferenzen", expanded=False):
    skill = st.select_slider(
        "Skill-Level",
        options=['beginner', 'intermediate', 'expert'],
        value=user_prefs_data.get('skill_level', 'intermediate'),
        format_func=lambda x: {'beginner': 'Anfaenger', 'intermediate': 'Fortgeschritten', 'expert': 'Experte'}[x]
    )

    budget = st.select_slider(
        "Budget",
        options=['low', 'medium', 'high'],
        value=user_prefs_data.get('budget_level', 'medium'),
        format_func=lambda x: {'low': 'Sparsam (<45 EUR)', 'medium': 'Mittel (45-70 EUR)', 'high': 'Komfort (>70 EUR)'}[x]
    )

    st.write("**Was ist dir wichtig?**")
    col1, col2 = st.columns(2)
    with col1:
        apres = st.checkbox("Apres-Ski", value=user_prefs_data.get('prefer_apres_ski', False))
        family = st.checkbox("Familienfreundlich", value=user_prefs_data.get('prefer_family', False))
        snow = st.checkbox("Schneesicherheit", value=user_prefs_data.get('prefer_snow_guarantee', True))
    with col2:
        park = st.checkbox("Terrain Park", value=user_prefs_data.get('prefer_terrain_park', False))
        xc = st.checkbox("Langlauf", value=user_prefs_data.get('prefer_cross_country', False))

    min_slopes = st.slider("Min. Pistenkilometer", 0, 200,
                           user_prefs_data.get('min_slopes_km', 50))

    if st.button("💾 Praeferenzen speichern"):
        save_user_preferences(st.session_state['user_id'], {
            'skill_level': skill,
            'budget_level': budget,
            'prefer_apres_ski': apres,
            'prefer_family': family,
            'prefer_snow_guarantee': snow,
            'prefer_terrain_park': park,
            'prefer_cross_country': xc,
            'min_slopes_km': min_slopes
        })
        st.success("Gespeichert!")
        st.rerun()

# Create UserPreferences object
user_preferences = UserPreferences(
    skill_level=skill,
    budget_level=budget,
    prefer_apres_ski=apres,
    prefer_family=family,
    prefer_snow_guarantee=snow,
    prefer_terrain_park=park,
    prefer_cross_country=xc,
    min_slopes_km=min_slopes
)

# =============================================================================
# LOCATION SETUP
# =============================================================================

st.sidebar.subheader("Dein Standort")

# Default Location (Frankfurt)
default_lat = 50.1109
default_lon = 8.6821

if 'map_lat' not in st.session_state:
    st.session_state['map_lat'] = default_lat
if 'map_lon' not in st.session_state:
    st.session_state['map_lon'] = default_lon

# 1. Map for Location Selection
st.subheader("1. Waehle deinen Startort")

with st.expander("📍 Adresse suchen", expanded=True):
    c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
    street = c1.text_input("Strasse", placeholder="Hauptstr")
    number = c2.text_input("Nr", placeholder="1")
    zip_code = c3.text_input("PLZ", placeholder="10115")
    city = c4.text_input("Stadt", placeholder="Berlin")

    if st.button("Adresse finden"):
        if street and city:
            coords = geocode_address(street, number, zip_code, city)
            if coords:
                st.session_state['map_lat'] = coords[0]
                st.session_state['map_lon'] = coords[1]
                st.success(f"Gefunden: {street} {number}, {city} ({coords[0]:.4f}, {coords[1]:.4f})")
                st.rerun()
            else:
                st.error("Adresse nicht gefunden.")
        else:
            st.warning("Bitte mindestens Strasse und Stadt eingeben.")

st.info("Oder klicke auf die Karte um deinen Standort zu waehlen.")

m_start = folium.Map(location=[st.session_state['map_lat'], st.session_state['map_lon']], zoom_start=9)
folium.Marker(
    [st.session_state['map_lat'], st.session_state['map_lon']],
    popup="Dein Start",
    tooltip="Dein Standort",
    icon=folium.Icon(color="red", icon="home")
).add_to(m_start)

output = st_folium(m_start, height=300, width="100%", key="starter_map")

if output['last_clicked']:
    st.session_state['map_lat'] = output['last_clicked']['lat']
    st.session_state['map_lon'] = output['last_clicked']['lng']
    st.rerun()

user_lat = st.session_state['map_lat']
user_lon = st.session_state['map_lon']

st.write(f"Ausgewaehlter Standort: **{user_lat:.4f}, {user_lon:.4f}**")

max_dist = st.sidebar.slider("Max Entfernung (km)", 100, 1000, user_prefs_data.get('max_distance_km', 400))

# Trip Dates
st.sidebar.subheader("Reisedaten")
default_start = datetime.date(2026, 2, 14)
default_end = datetime.date(2026, 2, 21)
trip_dates = st.sidebar.date_input("Reisezeitraum", [default_start, default_end])

# Party Details
st.sidebar.subheader("Reisegruppe")
col1, col2 = st.sidebar.columns(2)
with col1:
    adults = st.number_input("Erwachsene", min_value=1, value=2)
    rooms = st.number_input("Zimmer", min_value=1, value=1)
with col2:
    children = st.number_input("Kinder", min_value=0, value=0)
    if children > 0:
        child_age = st.number_input("Alter Kind", min_value=0, value=10)
    else:
        child_age = 0

# =============================================================================
# LOAD DATA AND MODEL
# =============================================================================

resorts_df = get_ski_resorts()
resort_details_dict = get_all_resort_details()


@st.cache_resource
def get_cached_model(use_real_data):
    return load_or_train_model(use_real_data=use_real_data)


# Model settings
with st.sidebar.expander("Admin / Modell"):
    use_real_data = st.checkbox("Echte Wetterdaten (Open-Meteo)", value=False)
    if st.button("Modell neu trainieren"):
        with st.spinner("Trainiere Modell..."):
            get_cached_model.clear()
            snow_model = get_cached_model(use_real_data)
        st.success("Modell trainiert!")

snow_model = get_cached_model(use_real_data)

# Process dates
start_date = trip_dates[0] if isinstance(trip_dates, (list, tuple)) and len(trip_dates) > 0 else default_start
end_date = trip_dates[1] if isinstance(trip_dates, (list, tuple)) and len(trip_dates) > 1 else default_end
travel_month = start_date.month
nights = (end_date - start_date).days

# =============================================================================
# RESULTS
# =============================================================================

st.subheader("2. Gefundene Skigebiete & Routen")
filtered_resorts = filter_resorts_by_distance(resorts_df, user_lat, user_lon, max_dist)

if filtered_resorts.empty:
    st.warning("Keine Skigebiete in dieser Entfernung gefunden. Erhoehe die maximale Distanz!")
else:
    # Predict Snow
    filtered_resorts['predicted_snow_cm'] = filtered_resorts.apply(
        lambda row: predict_snow_quality(snow_model, travel_month, row['altitude_m'], row['lat']), axis=1
    )

    # Add full resort details for matching
    for idx, row in filtered_resorts.iterrows():
        details = resort_details_dict.get(row['name'], {})
        filtered_resorts.at[idx, 'peak_altitude_m'] = details.get('peak_altitude_m', row['altitude_m'] + 1000)

    # =============================================================================
    # PREFERENCE MATCHING (Level 2 - NEW)
    # =============================================================================

    matcher = ResortMatcher(user_preferences)
    match_results = []

    for idx, row in filtered_resorts.iterrows():
        resort_name = row['name']
        details = resort_details_dict.get(resort_name, row.to_dict())

        score_data = matcher.calculate_total_score(
            details,
            row.get('distance_km', 0),
            row.get('predicted_snow_cm', 0)
        )
        filtered_resorts.at[idx, 'match_score'] = score_data['total_score']

    # Sort by match score
    filtered_resorts = filtered_resorts.sort_values(by='match_score', ascending=False)

    # --- RESULTS MAP ---
    mid_lat = (user_lat + filtered_resorts.iloc[0]['lat']) / 2
    mid_lon = (user_lon + filtered_resorts.iloc[0]['lon']) / 2

    m_results = folium.Map(location=[mid_lat, mid_lon], zoom_start=6)

    folium.Marker(
        [user_lat, user_lon],
        popup="Dein Start",
        icon=folium.Icon(color="red", icon="home")
    ).add_to(m_results)

    for idx, row in filtered_resorts.iterrows():
        folium.Marker(
            [row['lat'], row['lon']],
            popup=f"<b>{row['name']}</b><br>Match: {row['match_score']:.0f}%<br>Schnee: {row['predicted_snow_cm']}cm",
            tooltip=row['name'],
            icon=folium.Icon(color="blue", icon="snowflake", prefix="fa")
        ).add_to(m_results)

        folium.PolyLine(
            locations=[(user_lat, user_lon), (row['lat'], row['lon'])],
            color="blue",
            weight=2,
            opacity=0.5,
            dash_array='5, 10'
        ).add_to(m_results)

    st_folium(m_results, height=400, width="100%", key="results_map")

    # --- RESULT TABLE with Selection ---
    st.write("### Klicke auf ein Resort fuer Details")

    display_df = filtered_resorts[['name', 'country', 'distance_km', 'altitude_m',
                                    'slopes_km', 'predicted_snow_cm', 'match_score']].copy()
    display_df.columns = ['Name', 'Land', 'Distanz (km)', 'Hoehe (m)',
                          'Pisten (km)', 'Schnee (cm)', 'Match (%)']

    selection = st.dataframe(
        display_df,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    selected_row_index = selection.selection.rows

    # =============================================================================
    # COMPARISON FEATURE (Level 2 - NEW)
    # =============================================================================

    st.write("### 🔄 Resorts vergleichen")
    compare_options = filtered_resorts['name'].tolist()

    selected_for_compare = st.multiselect(
        "Waehle 2-3 Resorts zum Vergleichen:",
        options=compare_options,
        max_selections=3
    )

    if len(selected_for_compare) >= 2:
        compare_resorts = []
        for name in selected_for_compare:
            details = resort_details_dict.get(name, {})
            resort_row = filtered_resorts[filtered_resorts['name'] == name].iloc[0]
            details['distance_km'] = resort_row['distance_km']
            details['predicted_snow_cm'] = resort_row['predicted_snow_cm']
            compare_resorts.append(details)

        with st.expander("📊 Vergleichsansicht", expanded=True):
            # Tabs for different comparison views
            comp_tab1, comp_tab2, comp_tab3 = st.tabs(["Uebersicht", "Schneebedingungen", "Preise & Unterkunft"])

            with comp_tab1:
                comparator = ResortComparator(compare_resorts, fetch_live_data=SNOW_API_AVAILABLE)

                # Comparison Table
                st.write("**Detailvergleich**")
                comparison_table = comparator.get_comparison_table()
                st.dataframe(comparison_table, use_container_width=True)

                # Winner
                result = comparator.calculate_winner()
                st.success(f"🏆 **Gesamtsieger: {result['winner']}** "
                          f"(Score: {result['scores'][result['winner']]:.0f}/100, "
                          f"Vorsprung: +{result['margin']:.0f})")

                # Pros/Cons
                cols = st.columns(len(compare_resorts))
                for i, (col, resort) in enumerate(zip(cols, compare_resorts)):
                    with col:
                        st.write(f"**{resort['name']}**")
                        pros_cons = comparator.get_pros_cons(resort['name'])
                        for pro in pros_cons['pros']:
                            st.write(f"✅ {pro}")
                        for con in pros_cons['cons']:
                            st.write(f"⚠️ {con}")

            with comp_tab2:
                st.write("**Echte Schneebedingungen im Vergleich**")

                if SNOW_API_AVAILABLE and comparator.snow_conditions:
                    # Snow comparison table
                    snow_rows = []
                    for name, condition in comparator.snow_conditions.items():
                        snow_rows.append({
                            'Resort': name,
                            'Score': f"{condition.overall_score:.0f}/100",
                            'Schnee Tal': f"{condition.snow_depth.base_depth_cm:.0f} cm",
                            'Schnee Berg': f"{condition.snow_depth.summit_depth_cm:.0f} cm",
                            'Neuschnee 7d': f"{condition.fresh_snow.last_7days_cm:.0f} cm",
                            'Lawinen': get_avalanche_risk_label(condition.avalanche.risk_level),
                            'Qualitaet': condition.snow_quality_rating,
                            'Pisten offen': f"{condition.piste.slope_availability:.0f}%"
                        })
                    st.dataframe(pd.DataFrame(snow_rows), use_container_width=True)

                    # Best findings
                    st.markdown("---")
                    conditions_list = list(comparator.snow_conditions.values())
                    best_snow = max(conditions_list, key=lambda c: c.snow_depth.average_depth_cm)
                    best_fresh = max(conditions_list, key=lambda c: c.fresh_snow.last_7days_cm)
                    safest = min(conditions_list, key=lambda c: c.avalanche.risk_level.value if c.avalanche.risk_level.value > 0 else 10)

                    finding_cols = st.columns(3)
                    finding_cols[0].info(f"Meiste Schnee: **{best_snow.resort_name}**")
                    finding_cols[1].info(f"Meiste Neuschnee: **{best_fresh.resort_name}**")
                    finding_cols[2].info(f"Sicherster: **{safest.resort_name}**")
                else:
                    st.warning("Erweiterte Schneebedingungen nicht verfuegbar. Aktiviere die Snow API.")

            with comp_tab3:
                st.write("**Preis- und Unterkunftsvergleich**")

                # Ski pass prices
                st.markdown("##### Skipass-Preise")
                pass_rows = []
                for resort in compare_resorts:
                    tp = resort.get('ticket_prices', {})
                    pass_rows.append({
                        'Resort': resort['name'],
                        'Tagespass': f"{tp.get('day_adult', 55)} EUR",
                        'Wochenpass': f"{tp.get('week_adult', 290)} EUR",
                        'Kind/Tag': f"{tp.get('day_child', 30)} EUR",
                        'Kind/Woche': f"{tp.get('week_child', 160)} EUR"
                    })
                st.dataframe(pd.DataFrame(pass_rows), use_container_width=True)

                # Accommodation prices
                if ACCOMMODATION_AVAILABLE:
                    st.markdown("##### Unterkunftskosten (Schaetzung)")

                    accom_search = AccommodationSearch()
                    checkin = date.today() + timedelta(days=30)
                    checkout = checkin + timedelta(days=nights if nights > 0 else 7)
                    travel_group = TravelGroup(adults=adults, children=children, rooms=rooms)

                    accom_rows = []
                    for resort in compare_resorts:
                        result = accom_search.search(resort, checkin, checkout, travel_group)
                        accom_rows.append({
                            'Resort': resort['name'],
                            'Budget': f"{result.price_range['min']:.0f} EUR",
                            'Standard': f"{result.price_range['average']:.0f} EUR",
                            'Premium': f"{result.price_range['max']:.0f} EUR",
                            'Pro Nacht': f"{result.price_range['average']/nights:.0f} EUR" if nights > 0 else "N/A"
                        })
                    st.dataframe(pd.DataFrame(accom_rows), use_container_width=True)

                    # Cheapest resort
                    cheapest = min(accom_rows, key=lambda x: float(x['Standard'].replace(' EUR', '')))
                    st.success(f"Guenstigste Unterkunft: **{cheapest['Resort']}** ({cheapest['Standard']})")

                    # Booking links
                    st.markdown("##### Direkt buchen")
                    link_cols = st.columns(len(compare_resorts))
                    for i, (col, resort) in enumerate(zip(link_cols, compare_resorts)):
                        with col:
                            booking_url = get_accommodation_url(
                                resort['name'],
                                checkin, checkout,
                                adults, children, rooms
                            )
                            st.link_button(f"Booking.com: {resort['name']}", booking_url)
                else:
                    st.info("Unterkunfts-Modul nicht verfuegbar.")

    # =============================================================================
    # RESORT DETAILS
    # =============================================================================

    selected_resort_name = None
    selected_resort_data = None

    if selected_row_index:
        selected_resort_data = filtered_resorts.iloc[selected_row_index[0]]
        selected_resort_name = selected_resort_data['name']

    if selected_resort_name:
        st.subheader(f"3. Details: {selected_resort_name}")

        resort_full_details = resort_details_dict.get(selected_resort_name, {})

        # Favorite & Save buttons
        col_fav, col_save, col_info = st.columns([1, 1, 3])
        with col_fav:
            is_fav = is_favorite(st.session_state['user_id'], selected_resort_name)
            if is_fav:
                if st.button("❤️ Favorit entfernen"):
                    remove_favorite(st.session_state['user_id'], selected_resort_name)
                    st.rerun()
            else:
                if st.button("🤍 Als Favorit"):
                    add_favorite(st.session_state['user_id'], selected_resort_name)
                    st.toast(f"{selected_resort_name} zu Favoriten hinzugefuegt!")

        with col_save:
            if st.button("💾 Trip speichern"):
                save_trip(st.session_state['user_id'], user_lat, user_lon,
                         selected_resort_name, start_date, end_date, adults, children)
                st.toast(f"Trip nach {selected_resort_name} gespeichert!")

        # Tabs for different info
        tab_hotels, tab_accom, tab_budget, tab_weather, tab_info, tab_reviews, tab_map = st.tabs([
            "🏨 Hotels", "🏠 Unterkunft", "💰 Budget", "❄️ Schnee & Wetter", "ℹ️ Info", "⭐ Bewertungen", "🗺️ Windy"
        ])

        with tab_hotels:
            hotels_df = generate_hotel_options(selected_resort_name, adults, children, rooms)
            for i, hotel in hotels_df.iterrows():
                with st.expander(f"{hotel['hotel_name']} - {hotel['price_total']} EUR"):
                    col_h1, col_h2 = st.columns([3, 1])
                    with col_h1:
                        st.write(f"**Sterne:** {'⭐' * int(hotel['stars'])}")
                        st.write(f"**Familienfreundlich:** {'✅' if hotel['family_friendly'] else '❌'}")
                        st.write(f"**Verfuegbare Zimmer:** {hotel['rooms_available']}")
                    with col_h2:
                        st.link_button("Booking.com", hotel['booking_url'])

        # =============================================================================
        # ACCOMMODATION TAB (Level 2.5 - NEW)
        # =============================================================================

        with tab_accom:
            st.markdown("### 🏠 Unterkunftssuche")

            if ACCOMMODATION_AVAILABLE:
                st.markdown(f"Finde die beste Unterkunft in **{selected_resort_name}**")

                # Search parameters
                accom_col1, accom_col2 = st.columns(2)

                with accom_col1:
                    st.write("**Reisedaten:**")
                    accom_checkin = st.date_input(
                        "Check-in",
                        value=start_date,
                        key="accom_checkin"
                    )
                    accom_checkout = st.date_input(
                        "Check-out",
                        value=end_date,
                        key="accom_checkout"
                    )
                    accom_nights = (accom_checkout - accom_checkin).days

                with accom_col2:
                    st.write("**Reisegruppe:**")
                    accom_adults = st.number_input("Erwachsene", 1, 10, adults, key="accom_adults")
                    accom_children = st.number_input("Kinder", 0, 10, children, key="accom_children")
                    accom_rooms = st.number_input("Zimmer/Einheiten", 1, 5, rooms, key="accom_rooms")

                # Create search
                accom_search = AccommodationSearch()
                travel_group = TravelGroup(
                    adults=accom_adults,
                    children=accom_children,
                    rooms=accom_rooms
                )

                search_result = accom_search.search(
                    resort_full_details,
                    accom_checkin,
                    accom_checkout,
                    travel_group
                )

                st.markdown("---")

                # Price estimates
                st.markdown("#### Preisschaetzungen")
                st.caption(f"Fuer {accom_nights} Naechte, {accom_adults + accom_children} Personen")

                price_cols = st.columns(3)
                price_cols[0].metric(
                    "Budget",
                    f"{search_result.price_range['min']:.0f} EUR",
                    f"{search_result.price_range['min']/accom_nights:.0f} EUR/Nacht"
                )
                price_cols[1].metric(
                    "Standard",
                    f"{search_result.price_range['average']:.0f} EUR",
                    f"{search_result.price_range['average']/accom_nights:.0f} EUR/Nacht"
                )
                price_cols[2].metric(
                    "Premium",
                    f"{search_result.price_range['max']:.0f} EUR",
                    f"{search_result.price_range['max']/accom_nights:.0f} EUR/Nacht"
                )

                # Accommodation options
                st.markdown("#### Unterkunftsoptionen")

                for accom in search_result.accommodations:
                    with st.container():
                        ac_col1, ac_col2, ac_col3 = st.columns([3, 1, 1])
                        with ac_col1:
                            st.write(f"**{accom.name}**")
                            st.caption(f"Typ: {accom.accommodation_type}")
                            if accom.ski_in_out:
                                st.caption("Ski-in/Ski-out verfuegbar")
                        with ac_col2:
                            st.metric("Preis", f"{accom.price_total:.0f} EUR")
                        with ac_col3:
                            st.metric("Bewertung", f"{accom.rating}/10")
                        st.markdown("---")

                # Direct booking link
                st.markdown("#### Jetzt suchen auf Booking.com")

                booking_url = get_accommodation_url(
                    selected_resort_name,
                    accom_checkin,
                    accom_checkout,
                    accom_adults,
                    accom_children,
                    accom_rooms
                )

                st.link_button(
                    f"Alle Unterkuenfte in {selected_resort_name} anzeigen",
                    booking_url,
                    use_container_width=True
                )

                st.caption("Die Preise sind Schaetzungen. Aktuelle Preise auf Booking.com pruefen.")

            else:
                st.warning("Unterkunfts-Modul nicht verfuegbar.")
                st.info("Bitte stelle sicher, dass accommodation.py vorhanden ist.")

        # =============================================================================
        # BUDGET TAB (Level 2 - NEW)
        # =============================================================================

        with tab_budget:
            st.markdown("### 💰 Reise-Budgetplaner")

            col_opts, col_transport = st.columns(2)

            with col_opts:
                st.write("**Optionen:**")
                rent_equip = st.checkbox("Ausruestung leihen", value=True, key="budget_equip")
                ski_school_kids = st.checkbox("Skischule Kinder", value=children > 0, key="budget_school_kids")
                ski_school_adults = st.checkbox("Skischule Erwachsene", value=False, key="budget_school_adults")
                half_board = st.checkbox("Halbpension", value=True, key="budget_hb")
                insurance = st.checkbox("Ski-Versicherung", value=True, key="budget_ins")

            with col_transport:
                st.write("**Anreise:**")
                transport = st.radio(
                    "Transportmittel",
                    options=['Auto', 'Bahn', 'Bus', 'Flug'],
                    horizontal=True,
                    key="budget_transport"
                )
                transport_map = {
                    'Auto': TransportMode.CAR,
                    'Bahn': TransportMode.TRAIN,
                    'Bus': TransportMode.BUS,
                    'Flug': TransportMode.FLIGHT
                }

                accommodation = st.radio(
                    "Unterkunft",
                    options=['Hotel', 'Ferienwohnung', 'Hostel'],
                    horizontal=True,
                    key="budget_accom"
                )
                accom_map = {'Hotel': 'hotel', 'Ferienwohnung': 'apartment', 'Hostel': 'hostel'}

            # Calculate budget
            party = TravelParty(adults=adults, children=children,
                               child_ages=[child_age] * children if children > 0 else [])

            trip_details = TripDetails(
                nights=nights,
                ski_days=max(1, nights - 1),
                distance_km=selected_resort_data['distance_km']
            )

            budget_options = BudgetOptions(
                rent_equipment=rent_equip,
                ski_school_adults=ski_school_adults,
                ski_school_children=ski_school_kids,
                half_board=half_board,
                ski_insurance=insurance,
                accommodation_type=accom_map[accommodation]
            )

            budget_result = get_budget_summary(
                resort=resort_full_details,
                party=party,
                trip=trip_details,
                options=budget_options,
                transport_mode=transport_map[transport]
            )

            st.markdown("---")

            # Total costs
            total_col, pp_col, night_col = st.columns(3)
            total_col.metric("💶 Gesamtkosten", f"{budget_result['total']:,.0f} EUR")
            pp_col.metric("👤 Pro Person", f"{budget_result['per_person']:,.0f} EUR")
            night_col.metric("🌙 Pro Nacht", f"{budget_result['per_night']:,.0f} EUR")

            # Breakdown chart
            st.write("**Kostenaufschluesselung:**")
            breakdown_df = pd.DataFrame({
                'Kategorie': list(budget_result['breakdown'].keys()),
                'Kosten': list(budget_result['breakdown'].values())
            })
            breakdown_df = breakdown_df[breakdown_df['Kosten'] > 0]
            st.bar_chart(breakdown_df.set_index('Kategorie'))

            # Transport comparison
            with st.expander("🚗 Anreise-Vergleich"):
                transport_df = pd.DataFrame({
                    'Transportmittel': ['Auto', 'Bahn', 'Bus', 'Flug'],
                    'Kosten (EUR)': [
                        budget_result['transport_comparison']['car'],
                        budget_result['transport_comparison']['train'],
                        budget_result['transport_comparison']['bus'],
                        budget_result['transport_comparison']['flight']
                    ]
                })
                st.dataframe(transport_df, use_container_width=True)

                cheapest = min(budget_result['transport_comparison'],
                              key=budget_result['transport_comparison'].get)
                st.success(f"💡 Guenstigste Option: **{cheapest.title()}** "
                          f"({budget_result['transport_comparison'][cheapest]:,.0f} EUR)")

            # Savings tips
            if budget_result.get('savings_tips'):
                st.write("**💡 Spartipps:**")
                for tip in budget_result['savings_tips']:
                    st.info(tip)

        with tab_weather:
            st.markdown("### Schneebedingungen & Wetter")
            lat = selected_resort_data['lat']
            lon = selected_resort_data['lon']

            # Enhanced snow data (Level 2.5)
            if SNOW_API_AVAILABLE:
                with st.spinner("Lade erweiterte Schneebedingungen..."):
                    snow_data = get_enhanced_snow_data(resort_full_details)

                if snow_data and snow_data.get('is_enhanced'):
                    # Overall score
                    score = snow_data.get('overall_score', 0)
                    summary = snow_data.get('condition_summary', '')
                    quality = snow_data.get('snow_quality_rating', '')

                    st.markdown(f"#### Bewertung: **{score:.0f}/100** - {summary}")
                    st.caption(f"Schneequalitaet: {quality}")

                    # Snow depths
                    st.markdown("##### Schneehoehen")
                    snow_cols = st.columns(3)
                    snow_cols[0].metric(
                        f"Tal ({snow_data.get('base_altitude_m', 0)}m)",
                        f"{snow_data.get('snow_depth_base_cm', 0):.0f} cm"
                    )
                    snow_cols[1].metric(
                        f"Mitte ({snow_data.get('mid_altitude_m', 0)}m)",
                        f"{snow_data.get('snow_depth_mid_cm', 0):.0f} cm"
                    )
                    snow_cols[2].metric(
                        f"Berg ({snow_data.get('summit_altitude_m', 0)}m)",
                        f"{snow_data.get('snow_depth_summit_cm', 0):.0f} cm"
                    )

                    # Fresh snow
                    st.markdown("##### Neuschnee")
                    fresh_cols = st.columns(4)
                    fresh_cols[0].metric("24h", f"{snow_data.get('fresh_snow_24h_cm', 0):.0f} cm")
                    fresh_cols[1].metric("48h", f"{snow_data.get('fresh_snow_48h_cm', 0):.0f} cm")
                    fresh_cols[2].metric("7 Tage", f"{snow_data.get('fresh_snow_7days_cm', 0):.0f} cm")
                    fresh_cols[3].metric("Trend", snow_data.get('snowfall_trend', 'stable').replace('_', ' ').title())

                    # Forecast
                    st.markdown("##### Schneefall-Vorhersage")
                    forecast_cols = st.columns(3)
                    forecast_cols[0].metric("Naechste 24h", f"{snow_data.get('forecast_snow_24h_cm', 0):.0f} cm")
                    forecast_cols[1].metric("Naechste 48h", f"{snow_data.get('forecast_snow_48h_cm', 0):.0f} cm")
                    forecast_cols[2].metric("Naechste 7 Tage", f"{snow_data.get('forecast_snow_7days_cm', 0):.0f} cm")

                    # Avalanche risk
                    st.markdown("##### Lawinenrisiko")
                    risk_level = snow_data.get('avalanche_risk_level', 0)
                    risk_label = snow_data.get('avalanche_risk_label', 'Keine Daten')
                    risk_desc = snow_data.get('avalanche_description', '')

                    risk_color = get_avalanche_risk_color(
                        __import__('snow_conditions').AvalancheRisk(risk_level)
                    ) if risk_level > 0 else "#808080"

                    st.markdown(f"<span style='background-color:{risk_color};padding:5px 10px;border-radius:5px;color:white'>{risk_label}</span>", unsafe_allow_html=True)
                    if risk_desc:
                        st.caption(risk_desc)

                    if snow_data.get('freeride_warning'):
                        st.warning("Freeride nicht empfohlen bei aktueller Lawinensituation!")

                    # Piste conditions
                    st.markdown("##### Pistenstatus")
                    piste_cols = st.columns(4)
                    piste_cols[0].metric("Status", snow_data.get('piste_status', 'unknown').title())
                    piste_cols[1].metric("Lifte offen", f"{snow_data.get('open_lifts', 0)}/{snow_data.get('total_lifts', 0)}")
                    piste_cols[2].metric("Pisten offen", f"{snow_data.get('open_slopes_km', 0):.0f}/{snow_data.get('total_slopes_km', 0):.0f} km")
                    piste_cols[3].metric("Verfuegbarkeit", f"{snow_data.get('slope_availability_percent', 0):.0f}%")

                    # Data quality info
                    st.markdown("---")
                    confidence = snow_data.get('confidence_score', 0)
                    sources = ", ".join(snow_data.get('data_sources', []))
                    st.caption(f"Datenqualitaet: {confidence:.0%} | Quellen: {sources}")

                else:
                    st.info("Erweiterte Schneebedingungen nicht verfuegbar. Zeige Basisdaten.")

            # Basic weather data (fallback)
            st.markdown("---")
            st.markdown("#### Wetter & 7-Tage Vorhersage")

            with st.spinner("Lade Wetterdaten..."):
                current_w, df_forecast = get_live_weather(lat, lon)

            if current_w:
                w1, w2, w3 = st.columns(3)
                w1.metric("Temperatur", f"{current_w['temp']} °C")
                w2.metric("Wind", f"{current_w['wind']} km/h")
                w3.metric("Schneehoehe (Basis)", f"{current_w['snow_depth'] * 100:.1f} cm")

                st.write("#### 7-Tage Vorhersage")
                st.dataframe(df_forecast, use_container_width=True)
            else:
                st.error("Wetterdaten nicht verfuegbar.")

        with tab_info:
            st.markdown(f"### Ueber {selected_resort_name}")
            with st.spinner("Lade Wikipedia..."):
                wiki_text = get_wiki_summary(selected_resort_name)
            st.info(wiki_text)

            st.markdown("### Statistiken")
            col_s1, col_s2, col_s3 = st.columns(3)
            col_s1.metric("Hoehe Tal", f"{selected_resort_data['altitude_m']} m")
            col_s2.metric("Pisten", f"{selected_resort_data.get('slopes_km', 'N/A')} km")
            col_s3.metric("Lifte", f"{selected_resort_data.get('lifts', 'N/A')}")

            # Additional details from JSON
            if resort_full_details:
                st.markdown("### Features")
                features = resort_full_details.get('features', {})
                ratings = resort_full_details.get('ratings', {})

                feat_col1, feat_col2 = st.columns(2)
                with feat_col1:
                    st.write(f"**Beschneiung:** {features.get('snow_cannons_km', 0)} km")
                    st.write(f"**Gletscher:** {'Ja' if features.get('glacier') else 'Nein'}")
                    st.write(f"**Terrain Park:** {'Ja' if features.get('terrain_park') else 'Nein'}")
                with feat_col2:
                    st.write(f"**Nachtski:** {'Ja' if features.get('night_skiing') else 'Nein'}")
                    st.write(f"**Langlauf:** {features.get('cross_country_km', 0)} km")

                st.markdown("### Bewertungen")
                rat_cols = st.columns(4)
                rat_cols[0].metric("Apres-Ski", f"{ratings.get('apres_ski', 3)}/5")
                rat_cols[1].metric("Familie", f"{ratings.get('family_friendly', 3)}/5")
                rat_cols[2].metric("Schnee", f"{ratings.get('snow_reliability', 3)}/5")
                rat_cols[3].metric("Preis-Leistung", f"{ratings.get('value_for_money', 3)}/5")

        # =============================================================================
        # REVIEWS TAB (Level 2 - NEW)
        # =============================================================================

        with tab_reviews:
            st.markdown(f"### ⭐ Bewertungen fuer {selected_resort_name}")

            summary = get_resort_rating_summary(selected_resort_name)

            if summary['count'] > 0:
                col1, col2, col3 = st.columns([1, 2, 1])

                with col1:
                    st.metric("Gesamtbewertung", f"{summary['overall']}/5 ⭐")
                    st.caption(f"Basierend auf {summary['count']} Bewertungen")

                with col2:
                    st.write("**Detail-Bewertungen:**")
                    for label, key in [('Schnee', 'snow'), ('Lifte', 'lift'),
                                       ('Gastronomie', 'food'), ('Preis-Leistung', 'value')]:
                        val = summary.get(key, 0)
                        st.progress(val/5, text=f"{label}: {val}/5")

                with col3:
                    st.metric("Empfehlung", f"{summary['recommend_pct']:.0f}%")
            else:
                st.info("Noch keine Bewertungen vorhanden. Sei der Erste!")

            st.markdown("---")

            reviews = get_resort_reviews(selected_resort_name)
            for review in reviews:
                with st.container():
                    col_user, col_rating = st.columns([3, 1])
                    with col_user:
                        st.write(f"**{review.get('review_title') or 'Bewertung'}**")
                        st.caption(f"von {review['username']} am {str(review['created_at'])[:10]}")
                    with col_rating:
                        st.write("⭐" * int(review['overall_rating']))

                    st.write(review['review_text'])

                    if review['pros'] or review['cons']:
                        p_col, c_col = st.columns(2)
                        with p_col:
                            for pro in review['pros']:
                                st.write(f"✅ {pro}")
                        with c_col:
                            for con in review['cons']:
                                st.write(f"❌ {con}")

                    st.markdown("---")

            # Write own review
            with st.expander("✍️ Eigene Bewertung schreiben"):
                review_title = st.text_input("Titel", placeholder="Toller Skiurlaub!", key="review_title")

                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    overall = st.slider("Gesamtbewertung", 1, 5, 4, key="review_overall")
                    snow_r = st.slider("Schneeverhaeltnisse", 1, 5, 4, key="review_snow")
                    lift_r = st.slider("Lifte & Infrastruktur", 1, 5, 4, key="review_lift")
                with col_r2:
                    food_r = st.slider("Gastronomie", 1, 5, 4, key="review_food")
                    value_r = st.slider("Preis-Leistung", 1, 5, 4, key="review_value")
                    recommend = st.checkbox("Wuerde ich weiterempfehlen", value=True, key="review_rec")

                review_text = st.text_area("Deine Erfahrung", height=150, key="review_text")

                pros_input = st.text_input("Positives (kommagetrennt)",
                                           placeholder="Tolle Pisten, nettes Personal", key="review_pros")
                cons_input = st.text_input("Negatives (kommagetrennt)",
                                           placeholder="Lange Warteschlangen", key="review_cons")

                if st.button("Bewertung absenden"):
                    if review_text:
                        submit_review(
                            st.session_state['user_id'],
                            selected_resort_name,
                            {'overall': overall, 'snow': snow_r, 'lift': lift_r,
                             'food': food_r, 'value': value_r},
                            review_text,
                            title=review_title,
                            recommend=recommend,
                            pros=[p.strip() for p in pros_input.split(',') if p.strip()],
                            cons=[c.strip() for c in cons_input.split(',') if c.strip()]
                        )
                        st.success("Danke fuer deine Bewertung!")
                        st.rerun()
                    else:
                        st.warning("Bitte schreibe einen Bewertungstext.")

        with tab_map:
            st.markdown("### Live Wind & Wetter Karte (Windy.com)")
            lat = selected_resort_data['lat']
            lon = selected_resort_data['lon']
            windy_url = f"https://embed.windy.com/embed2.html?lat={lat}&lon={lon}&detailLat={lat}&detailLon={lon}&width=650&height=450&zoom=11&level=surface&overlay=wind&product=ecmwf&menu=&message=&marker=&calendar=now&pressure=&type=map&location=coordinates&detail=&metricWind=default&metricTemp=default&radarRange=-1"
            components.iframe(windy_url, height=500)

# =============================================================================
# SIDEBAR: SAVED TRIPS & FAVORITES
# =============================================================================

st.sidebar.markdown("---")

# Favorites
st.sidebar.subheader("❤️ Favoriten")
favorites = get_user_favorites(st.session_state['user_id'])
if favorites:
    for fav in favorites[:5]:
        st.sidebar.text(f"⭐ {fav}")
else:
    st.sidebar.text("Keine Favoriten")

# Saved trips
st.sidebar.subheader("📍 Gespeicherte Trips")
user_trips = get_user_trips(st.session_state['user_id'])
if user_trips:
    for trip in user_trips[:5]:
        st.sidebar.text(f"🎿 {trip[0]}\n📅 {trip[1]}")
else:
    st.sidebar.text("Keine gespeicherten Trips")
