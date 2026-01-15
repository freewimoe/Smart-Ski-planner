"""
Smart Ski Vacation Planner 2026 - Level 2
Enhanced with preferences, budget planning, and resort comparison.
"""

import streamlit as st
import pandas as pd
import datetime
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
from weather import get_live_weather

# Level 2 imports
from preferences import UserPreferences, ResortMatcher
from budget import (
    TravelParty, TripDetails, BudgetOptions,
    TransportMode, get_budget_summary
)
from compare import ResortComparator

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
            comparator = ResortComparator(compare_resorts)

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
        tab_hotels, tab_budget, tab_weather, tab_info, tab_reviews, tab_map = st.tabs([
            "🏨 Hotels", "💰 Budget", "🌤️ Wetter", "ℹ️ Info", "⭐ Bewertungen", "🗺️ Windy"
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
            st.markdown("### Aktuelles Wetter & 7-Tage Vorhersage")
            lat = selected_resort_data['lat']
            lon = selected_resort_data['lon']

            with st.spinner("Lade Wetterdaten..."):
                current_w, df_forecast = get_live_weather(lat, lon)

            if current_w:
                w1, w2, w3 = st.columns(3)
                w1.metric("Temperatur", f"{current_w['temp']} °C")
                w2.metric("Wind", f"{current_w['wind']} km/h")
                w3.metric("Schneehoehe", f"{current_w['snow_depth'] * 100:.1f} cm")

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
