import requests
import pandas as pd
from typing import Dict, Optional, Tuple
from datetime import datetime

# Import snow condition modules
try:
    from snow_api import SnowConditionAggregator, get_snow_conditions
    from snow_conditions import NormalizedSnowCondition, get_avalanche_risk_label
    SNOW_API_AVAILABLE = True
except ImportError:
    SNOW_API_AVAILABLE = False


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


def get_enhanced_snow_data(resort: Dict) -> Optional[Dict]:
    """
    Fetches enhanced snow condition data for a resort.
    Uses the SnowConditionAggregator for comprehensive data.

    Args:
        resort: Dict with resort data (name, lat, lon, altitude_m, peak_altitude_m)

    Returns:
        Dict with comprehensive snow data or None if unavailable
    """
    if not SNOW_API_AVAILABLE:
        return _get_basic_snow_data(resort)

    try:
        condition = get_snow_conditions(resort)
        return _format_snow_condition(condition)
    except Exception as e:
        print(f"Enhanced snow data error: {e}")
        return _get_basic_snow_data(resort)


def _get_basic_snow_data(resort: Dict) -> Optional[Dict]:
    """Fallback to basic snow data from Open-Meteo."""
    lat = resort.get('lat', 0)
    lon = resort.get('lon', 0)

    current, forecast = get_live_weather(lat, lon)
    if not current:
        return None

    # Sum snowfall from forecast
    total_snowfall = 0
    if forecast is not None and 'Snowfall (cm)' in forecast.columns:
        total_snowfall = forecast['Snowfall (cm)'].sum()

    return {
        'snow_depth_cm': current.get('snow_depth', 0) * 100,  # Convert m to cm
        'fresh_snow_7days_cm': total_snowfall,
        'temperature_c': current.get('temp', 0),
        'wind_kmh': current.get('wind', 0),
        'data_source': 'open-meteo-basic',
        'is_enhanced': False
    }


def _format_snow_condition(condition: NormalizedSnowCondition) -> Dict:
    """Format NormalizedSnowCondition for display."""
    return {
        # Snow depths
        'snow_depth_base_cm': condition.snow_depth.base_depth_cm,
        'snow_depth_mid_cm': condition.snow_depth.mid_depth_cm,
        'snow_depth_summit_cm': condition.snow_depth.summit_depth_cm,
        'snow_depth_avg_cm': condition.snow_depth.average_depth_cm,

        # Altitudes
        'base_altitude_m': condition.snow_depth.base_altitude_m,
        'mid_altitude_m': condition.snow_depth.mid_altitude_m,
        'summit_altitude_m': condition.snow_depth.summit_altitude_m,

        # Fresh snow
        'fresh_snow_24h_cm': condition.fresh_snow.last_24h_cm,
        'fresh_snow_48h_cm': condition.fresh_snow.last_48h_cm,
        'fresh_snow_7days_cm': condition.fresh_snow.last_7days_cm,

        # Forecast
        'forecast_snow_24h_cm': condition.fresh_snow.next_24h_cm,
        'forecast_snow_48h_cm': condition.fresh_snow.next_48h_cm,
        'forecast_snow_7days_cm': condition.fresh_snow.next_7days_cm,
        'snowfall_trend': condition.fresh_snow.snowfall_trend,

        # Avalanche
        'avalanche_risk_level': condition.avalanche.risk_level.value,
        'avalanche_risk_name': condition.avalanche.risk_level.name,
        'avalanche_risk_label': get_avalanche_risk_label(condition.avalanche.risk_level),
        'avalanche_description': condition.avalanche.risk_description,
        'avalanche_problems': condition.avalanche.problem_types,
        'is_safe_for_piste': condition.avalanche.is_safe_for_piste,
        'freeride_warning': condition.avalanche.freeride_warning,

        # Piste conditions
        'piste_status': condition.piste.status.value,
        'open_lifts': condition.piste.open_lifts,
        'total_lifts': condition.piste.total_lifts,
        'open_slopes_km': condition.piste.open_slopes_km,
        'total_slopes_km': condition.piste.total_slopes_km,
        'lift_availability_percent': condition.piste.lift_availability,
        'slope_availability_percent': condition.piste.slope_availability,

        # Weather
        'temperature_c': condition.current_temp_c,
        'freezing_level_m': condition.freezing_level_m,
        'wind_kmh': condition.wind_speed_kmh,
        'visibility_km': condition.visibility_km,
        'weather_description': condition.weather_description,

        # Quality metrics
        'overall_score': condition.overall_score,
        'condition_summary': condition.condition_summary,
        'snow_quality_rating': condition.snow_quality_rating,

        # Metadata
        'confidence_score': condition.confidence_score,
        'data_sources': condition.data_sources,
        'last_updated': condition.last_updated.isoformat() if condition.last_updated else None,
        'is_enhanced': True
    }


def get_snow_comparison_data(resorts: list) -> Dict:
    """
    Get comparable snow data for multiple resorts.

    Args:
        resorts: List of resort dicts

    Returns:
        Dict with comparison data and rankings
    """
    if not SNOW_API_AVAILABLE:
        return {'error': 'Snow API not available', 'resorts': []}

    try:
        from snow_api import get_snow_comparison
        return get_snow_comparison(resorts)
    except Exception as e:
        print(f"Snow comparison error: {e}")
        return {'error': str(e), 'resorts': []}


def format_snow_display(snow_data: Dict) -> Dict[str, str]:
    """
    Format snow data for UI display.

    Returns:
        Dict with formatted strings for display
    """
    if not snow_data:
        return {'error': 'Keine Daten verfuegbar'}

    is_enhanced = snow_data.get('is_enhanced', False)

    display = {}

    if is_enhanced:
        # Enhanced display with all data
        display['snow_depth'] = (
            f"Tal: {snow_data.get('snow_depth_base_cm', 0):.0f}cm | "
            f"Mitte: {snow_data.get('snow_depth_mid_cm', 0):.0f}cm | "
            f"Berg: {snow_data.get('snow_depth_summit_cm', 0):.0f}cm"
        )

        display['fresh_snow'] = (
            f"24h: {snow_data.get('fresh_snow_24h_cm', 0):.0f}cm | "
            f"48h: {snow_data.get('fresh_snow_48h_cm', 0):.0f}cm | "
            f"7 Tage: {snow_data.get('fresh_snow_7days_cm', 0):.0f}cm"
        )

        display['forecast'] = (
            f"Naechste 24h: {snow_data.get('forecast_snow_24h_cm', 0):.0f}cm | "
            f"48h: {snow_data.get('forecast_snow_48h_cm', 0):.0f}cm | "
            f"7 Tage: {snow_data.get('forecast_snow_7days_cm', 0):.0f}cm"
        )

        display['avalanche'] = snow_data.get('avalanche_risk_label', 'Keine Daten')

        display['piste'] = (
            f"Lifte: {snow_data.get('open_lifts', 0)}/{snow_data.get('total_lifts', 0)} | "
            f"Pisten: {snow_data.get('open_slopes_km', 0):.0f}/{snow_data.get('total_slopes_km', 0):.0f}km"
        )

        display['weather'] = (
            f"{snow_data.get('temperature_c', 0):.1f}°C | "
            f"Wind: {snow_data.get('wind_kmh', 0):.0f}km/h | "
            f"{snow_data.get('weather_description', '')}"
        )

        display['quality'] = (
            f"Score: {snow_data.get('overall_score', 0):.0f}/100 | "
            f"{snow_data.get('condition_summary', '')} | "
            f"Schnee: {snow_data.get('snow_quality_rating', '')}"
        )

        display['confidence'] = f"{snow_data.get('confidence_score', 0):.0%}"
        display['sources'] = ", ".join(snow_data.get('data_sources', []))

    else:
        # Basic display
        display['snow_depth'] = f"Schneehoehe: {snow_data.get('snow_depth_cm', 0):.0f}cm"
        display['fresh_snow'] = f"Neuschnee 7 Tage: {snow_data.get('fresh_snow_7days_cm', 0):.0f}cm"
        display['weather'] = f"{snow_data.get('temperature_c', 0):.1f}°C | Wind: {snow_data.get('wind_kmh', 0):.0f}km/h"
        display['sources'] = snow_data.get('data_source', 'unbekannt')

    return display
