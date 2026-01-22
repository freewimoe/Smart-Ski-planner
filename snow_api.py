"""
Snow Condition API Aggregator
Fetches real snow data from multiple free sources.
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
import os

from snow_conditions import (
    NormalizedSnowCondition,
    SnowDepthData,
    FreshSnowData,
    AvalancheData,
    PisteCondition,
    AvalancheRisk,
    PisteStatus,
    estimate_snow_depth_at_altitude
)


# =============================================================================
# CACHE MANAGEMENT
# =============================================================================

@dataclass
class CacheEntry:
    """Cache entry with expiration."""
    data: Dict
    expires: datetime
    source: str


class SnowDataCache:
    """Simple in-memory cache for API responses."""

    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Dict]:
        """Get cached data if not expired."""
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() < entry.expires:
                return entry.data
            else:
                del self._cache[key]
        return None

    def set(self, key: str, data: Dict, ttl_minutes: int = 30, source: str = ""):
        """Cache data with TTL."""
        self._cache[key] = CacheEntry(
            data=data,
            expires=datetime.now() + timedelta(minutes=ttl_minutes),
            source=source
        )

    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()


# Global cache instance
_cache = SnowDataCache()


# =============================================================================
# OPEN-METEO SNOW FETCHER (FREE, NO API KEY)
# =============================================================================

class OpenMeteoSnowFetcher:
    """
    Fetches snow and weather data from Open-Meteo API.
    Free, no API key required.
    https://open-meteo.com/
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self):
        self.session = requests.Session()

    def fetch_snow_data(self, lat: float, lon: float, altitude_m: int = 1500) -> Optional[Dict]:
        """
        Fetch snow-related weather data for a location.

        Args:
            lat: Latitude
            lon: Longitude
            altitude_m: Altitude for elevation adjustment

        Returns:
            Dict with snow and weather data
        """
        cache_key = f"openmeteo_{lat}_{lon}"
        cached = _cache.get(cache_key)
        if cached:
            return cached

        try:
            params = {
                'latitude': lat,
                'longitude': lon,
                'hourly': 'temperature_2m,snowfall,snow_depth,weathercode,visibility,windspeed_10m',
                'daily': 'temperature_2m_max,temperature_2m_min,snowfall_sum,precipitation_sum,weathercode',
                'current_weather': 'true',
                'timezone': 'Europe/Berlin',
                'forecast_days': 7
            }

            response = self.session.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Process the response
            result = self._process_response(data, altitude_m)
            _cache.set(cache_key, result, ttl_minutes=30, source="open-meteo")

            return result

        except requests.RequestException as e:
            print(f"Open-Meteo API error: {e}")
            return None

    def _process_response(self, data: Dict, altitude_m: int) -> Dict:
        """Process Open-Meteo API response into our format."""
        current = data.get('current_weather', {})
        hourly = data.get('hourly', {})
        daily = data.get('daily', {})

        # Get current snow depth (if available)
        snow_depths = hourly.get('snow_depth', [])
        current_snow_depth = snow_depths[0] if snow_depths else 0

        # Sum snowfall for different periods
        snowfall_hourly = hourly.get('snowfall', [])

        # Calculate snowfall sums
        last_24h = sum(snowfall_hourly[:24]) if len(snowfall_hourly) >= 24 else sum(snowfall_hourly)
        last_48h = sum(snowfall_hourly[:48]) if len(snowfall_hourly) >= 48 else sum(snowfall_hourly)

        # Daily snowfall for 7 days
        daily_snowfall = daily.get('snowfall_sum', [])
        last_7days = sum(daily_snowfall[:7]) if daily_snowfall else 0

        # Forecast snowfall (next days)
        next_24h = sum(snowfall_hourly[24:48]) if len(snowfall_hourly) >= 48 else 0
        next_48h = sum(snowfall_hourly[24:72]) if len(snowfall_hourly) >= 72 else 0
        next_7days = sum(daily_snowfall[1:]) if len(daily_snowfall) > 1 else 0

        # Current conditions
        temp = current.get('temperature', 0)
        windspeed = current.get('windspeed', 0)
        weathercode = current.get('weathercode', 0)

        # Visibility (current hour)
        visibilities = hourly.get('visibility', [])
        visibility_m = visibilities[0] if visibilities else 10000
        visibility_km = visibility_m / 1000

        # Estimate freezing level
        freezing_level = self._estimate_freezing_level(temp, altitude_m)

        return {
            'snow_depth_cm': current_snow_depth * 100,  # Convert m to cm
            'snowfall_last_24h_cm': last_24h * 10,  # Convert to cm
            'snowfall_last_48h_cm': last_48h * 10,
            'snowfall_last_7days_cm': last_7days * 10,
            'snowfall_next_24h_cm': next_24h * 10,
            'snowfall_next_48h_cm': next_48h * 10,
            'snowfall_next_7days_cm': next_7days * 10,
            'temperature_c': temp,
            'windspeed_kmh': windspeed,
            'visibility_km': visibility_km,
            'weathercode': weathercode,
            'weather_description': self._get_weather_description(weathercode),
            'freezing_level_m': freezing_level,
            'source': 'open-meteo',
            'timestamp': datetime.now().isoformat()
        }

    def _estimate_freezing_level(self, temp_at_station: float, station_altitude: int) -> int:
        """Estimate freezing level based on temperature and lapse rate."""
        # Standard atmosphere lapse rate: -6.5°C per 1000m
        lapse_rate = 6.5 / 1000
        if temp_at_station <= 0:
            return station_altitude
        # Altitude where temp would be 0°C
        freezing_level = station_altitude + (temp_at_station / lapse_rate)
        return int(freezing_level)

    def _get_weather_description(self, code: int) -> str:
        """Convert WMO weather code to description."""
        descriptions = {
            0: "Klar",
            1: "Ueberwiegend klar",
            2: "Teilweise bewoelkt",
            3: "Bewoelkt",
            45: "Nebel",
            48: "Nebel mit Reif",
            51: "Leichter Nieselregen",
            53: "Nieselregen",
            55: "Starker Nieselregen",
            61: "Leichter Regen",
            63: "Regen",
            65: "Starker Regen",
            71: "Leichter Schneefall",
            73: "Schneefall",
            75: "Starker Schneefall",
            77: "Schneegriesel",
            80: "Leichte Regenschauer",
            81: "Regenschauer",
            82: "Starke Regenschauer",
            85: "Leichte Schneeschauer",
            86: "Starke Schneeschauer",
            95: "Gewitter",
            96: "Gewitter mit leichtem Hagel",
            99: "Gewitter mit starkem Hagel"
        }
        return descriptions.get(code, "Unbekannt")


# =============================================================================
# EUREGIO AVALANCHE FETCHER (FREE, ALPS ONLY)
# =============================================================================

class EuregioAvalancheFetcher:
    """
    Fetches avalanche data from Euregio Avalanche Report.
    Covers: Tirol, Suedtirol, Trentino
    https://avalanche.report/
    """

    # API endpoints for different regions
    ENDPOINTS = {
        'tirol': 'https://avalanche.report/albina_files/latest/de.json',
        'suedtirol': 'https://avalanche.report/albina_files/latest/de.json',
        'trentino': 'https://avalanche.report/albina_files/latest/de.json'
    }

    # Region mapping based on coordinates
    REGION_BOUNDS = {
        'tirol': {'lat_min': 46.8, 'lat_max': 47.7, 'lon_min': 10.1, 'lon_max': 12.8},
        'suedtirol': {'lat_min': 46.2, 'lat_max': 47.1, 'lon_min': 10.4, 'lon_max': 12.5},
        'vorarlberg': {'lat_min': 46.8, 'lat_max': 47.5, 'lon_min': 9.5, 'lon_max': 10.3},
        'salzburg': {'lat_min': 47.0, 'lat_max': 47.8, 'lon_min': 12.0, 'lon_max': 14.0},
        'switzerland': {'lat_min': 45.8, 'lat_max': 47.8, 'lon_min': 5.9, 'lon_max': 10.5}
    }

    def __init__(self):
        self.session = requests.Session()

    def fetch_avalanche_data(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Fetch avalanche data for a location.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Dict with avalanche risk data
        """
        cache_key = f"avalanche_{lat:.2f}_{lon:.2f}"
        cached = _cache.get(cache_key)
        if cached:
            return cached

        region = self._determine_region(lat, lon)
        if not region:
            # Location not in covered area
            return self._get_default_avalanche_data()

        try:
            # Try to fetch from Euregio API
            response = self.session.get(
                'https://avalanche.report/albina_files/latest/de.json',
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            result = self._process_euregio_response(data, lat, lon)
            _cache.set(cache_key, result, ttl_minutes=120, source="euregio")

            return result

        except requests.RequestException as e:
            print(f"Euregio API error: {e}")
            return self._get_default_avalanche_data()

    def _determine_region(self, lat: float, lon: float) -> Optional[str]:
        """Determine which avalanche region covers this location."""
        for region, bounds in self.REGION_BOUNDS.items():
            if (bounds['lat_min'] <= lat <= bounds['lat_max'] and
                bounds['lon_min'] <= lon <= bounds['lon_max']):
                return region
        return None

    def _process_euregio_response(self, data: Dict, lat: float, lon: float) -> Dict:
        """Process Euregio API response."""
        # The Euregio API returns complex region-based data
        # We'll extract the most relevant info

        try:
            bulletins = data.get('bulletins', [])

            # Find the most relevant bulletin for this location
            # For simplicity, use the first bulletin's data
            if bulletins:
                bulletin = bulletins[0]
                danger_ratings = bulletin.get('dangerRatings', [])

                # Get the main danger rating
                if danger_ratings:
                    main_rating = danger_ratings[0]
                    risk_level = main_rating.get('mainValue', 'unknown')

                    # Map to our scale
                    risk_map = {
                        'low': 1,
                        'moderate': 2,
                        'considerable': 3,
                        'high': 4,
                        'very_high': 5
                    }
                    risk_int = risk_map.get(risk_level.lower(), 0)

                    # Get elevation info
                    elevation = main_rating.get('elevation', {})
                    elevation_bound = elevation.get('upperBound', '')

                    # Get problem types
                    problems = bulletin.get('avalancheProblems', [])
                    problem_types = [p.get('type', '') for p in problems[:3]]

                    return {
                        'risk_level': risk_int,
                        'risk_description': self._get_risk_description(risk_int),
                        'elevation_info': elevation_bound,
                        'problem_types': problem_types,
                        'valid_until': bulletin.get('validTime', {}).get('endTime', ''),
                        'bulletin_url': 'https://avalanche.report/',
                        'source': 'euregio',
                        'timestamp': datetime.now().isoformat()
                    }
        except (KeyError, IndexError):
            pass

        return self._get_default_avalanche_data()

    def _get_default_avalanche_data(self) -> Dict:
        """Return default avalanche data when API fails."""
        return {
            'risk_level': 0,
            'risk_description': 'Keine aktuellen Daten verfuegbar',
            'elevation_info': '',
            'problem_types': [],
            'valid_until': '',
            'bulletin_url': '',
            'source': 'default',
            'timestamp': datetime.now().isoformat()
        }

    def _get_risk_description(self, level: int) -> str:
        """Get description for risk level."""
        descriptions = {
            1: "Geringe Lawinengefahr. Guenstige Verhaeltnisse.",
            2: "Maessige Lawinengefahr. Ueberwiegend guenstige Verhaeltnisse.",
            3: "Erhebliche Lawinengefahr. Kritische Situation in Steilhaengen.",
            4: "Grosse Lawinengefahr. Sehr kritische Situation. Erfahrung erforderlich.",
            5: "Sehr grosse Lawinengefahr. Ausserordentlich kritisch. Verzicht empfohlen."
        }
        return descriptions.get(level, "Keine Daten verfuegbar")


# =============================================================================
# SLF AVALANCHE FETCHER (SWITZERLAND)
# =============================================================================

class SLFAvalancheFetcher:
    """
    Fetches avalanche data from Swiss SLF.
    https://www.slf.ch/
    """

    API_URL = "https://www.slf.ch/avalanche/mobile/bulletin_de.json"

    def __init__(self):
        self.session = requests.Session()

    def fetch_avalanche_data(self, lat: float, lon: float) -> Optional[Dict]:
        """Fetch avalanche data for Swiss locations."""
        # Check if location is in Switzerland
        if not (45.8 <= lat <= 47.8 and 5.9 <= lon <= 10.5):
            return None

        cache_key = f"slf_{lat:.2f}_{lon:.2f}"
        cached = _cache.get(cache_key)
        if cached:
            return cached

        try:
            response = self.session.get(self.API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            result = self._process_response(data)
            _cache.set(cache_key, result, ttl_minutes=120, source="slf")
            return result

        except requests.RequestException:
            return None

    def _process_response(self, data: Dict) -> Dict:
        """Process SLF response."""
        # SLF has a different format - simplified processing
        try:
            danger = data.get('bulletins', [{}])[0]
            return {
                'risk_level': danger.get('dangerLevel', 0),
                'risk_description': danger.get('description', ''),
                'source': 'slf',
                'timestamp': datetime.now().isoformat()
            }
        except (KeyError, IndexError):
            return {'risk_level': 0, 'source': 'slf'}


# =============================================================================
# MAIN AGGREGATOR
# =============================================================================

class SnowConditionAggregator:
    """
    Aggregates snow condition data from multiple sources.
    Provides normalized, comparable data across all resorts.
    """

    def __init__(self):
        self.meteo_fetcher = OpenMeteoSnowFetcher()
        self.euregio_fetcher = EuregioAvalancheFetcher()
        self.slf_fetcher = SLFAvalancheFetcher()

    def get_conditions(self, resort: Dict) -> NormalizedSnowCondition:
        """
        Get normalized snow conditions for a resort.

        Args:
            resort: Dict with resort data including:
                - name: Resort name
                - lat, lon: Coordinates
                - altitude_m: Base altitude
                - peak_altitude_m: Summit altitude

        Returns:
            NormalizedSnowCondition with all available data
        """
        name = resort.get('name', 'Unknown')
        lat = resort.get('lat', 0)
        lon = resort.get('lon', 0)
        base_alt = resort.get('altitude_m', 1000)
        peak_alt = resort.get('peak_altitude_m', base_alt + 1000)
        mid_alt = (base_alt + peak_alt) // 2

        # Initialize condition
        condition = NormalizedSnowCondition(
            resort_name=name,
            resort_id=resort.get('id', name.lower().replace(' ', '_')),
            last_updated=datetime.now()
        )

        sources_used = []
        confidence = 0.0

        # Fetch weather/snow data from Open-Meteo
        meteo_data = self.meteo_fetcher.fetch_snow_data(lat, lon, base_alt)
        if meteo_data:
            sources_used.append('open-meteo')
            confidence += 0.4

            # Calculate snow depths at different altitudes
            base_snow = meteo_data.get('snow_depth_cm', 0)

            # Estimate snow at higher altitudes (approx +3cm per 100m)
            gradient = 3.0
            mid_snow = estimate_snow_depth_at_altitude(base_snow, base_alt, mid_alt, gradient)
            peak_snow = estimate_snow_depth_at_altitude(base_snow, base_alt, peak_alt, gradient)

            condition.snow_depth = SnowDepthData(
                base_depth_cm=base_snow,
                mid_depth_cm=mid_snow,
                summit_depth_cm=peak_snow,
                base_altitude_m=base_alt,
                mid_altitude_m=mid_alt,
                summit_altitude_m=peak_alt,
                measurement_time=datetime.now()
            )

            condition.fresh_snow = FreshSnowData(
                last_24h_cm=meteo_data.get('snowfall_last_24h_cm', 0),
                last_48h_cm=meteo_data.get('snowfall_last_48h_cm', 0),
                last_7days_cm=meteo_data.get('snowfall_last_7days_cm', 0),
                next_24h_cm=meteo_data.get('snowfall_next_24h_cm', 0),
                next_48h_cm=meteo_data.get('snowfall_next_48h_cm', 0),
                next_7days_cm=meteo_data.get('snowfall_next_7days_cm', 0)
            )

            condition.current_temp_c = meteo_data.get('temperature_c', 0)
            condition.freezing_level_m = meteo_data.get('freezing_level_m', 0)
            condition.wind_speed_kmh = meteo_data.get('windspeed_kmh', 0)
            condition.visibility_km = meteo_data.get('visibility_km', 10)
            condition.weather_description = meteo_data.get('weather_description', '')

        # Fetch avalanche data
        avalanche_data = self.euregio_fetcher.fetch_avalanche_data(lat, lon)
        if not avalanche_data or avalanche_data.get('source') == 'default':
            # Try Swiss SLF
            avalanche_data = self.slf_fetcher.fetch_avalanche_data(lat, lon)

        if avalanche_data and avalanche_data.get('risk_level', 0) > 0:
            sources_used.append(avalanche_data.get('source', 'avalanche'))
            confidence += 0.3

            risk_level = avalanche_data.get('risk_level', 0)
            try:
                risk_enum = AvalancheRisk(risk_level)
            except ValueError:
                risk_enum = AvalancheRisk.UNKNOWN

            condition.avalanche = AvalancheData(
                risk_level=risk_enum,
                risk_description=avalanche_data.get('risk_description', ''),
                danger_elevations=avalanche_data.get('elevation_info', ''),
                problem_types=avalanche_data.get('problem_types', []),
                bulletin_url=avalanche_data.get('bulletin_url', '')
            )

        # Set piste condition (estimated based on snow data)
        condition.piste = self._estimate_piste_condition(condition, resort)
        if condition.piste.status != PisteStatus.UNKNOWN:
            confidence += 0.2

        # Fallback: use ML prediction if available in resort data
        if 'predicted_snow_cm' in resort and condition.snow_depth.average_depth_cm == 0:
            sources_used.append('ml-prediction')
            predicted = resort['predicted_snow_cm']
            condition.snow_depth = SnowDepthData(
                base_depth_cm=predicted * 0.7,
                mid_depth_cm=predicted,
                summit_depth_cm=predicted * 1.3,
                base_altitude_m=base_alt,
                mid_altitude_m=mid_alt,
                summit_altitude_m=peak_alt
            )
            confidence += 0.1

        condition.data_sources = sources_used
        condition.confidence_score = min(1.0, confidence)

        return condition

    def _estimate_piste_condition(self, condition: NormalizedSnowCondition,
                                   resort: Dict) -> PisteCondition:
        """Estimate piste condition based on snow and weather data."""
        avg_snow = condition.snow_depth.average_depth_cm
        temp = condition.current_temp_c
        fresh = condition.fresh_snow.last_48h_cm

        total_slopes = resort.get('slopes_km', 100)
        total_lifts = resort.get('lifts', 20)

        # Estimate open percentage based on snow
        if avg_snow >= 80:
            open_percent = 95
        elif avg_snow >= 50:
            open_percent = 80
        elif avg_snow >= 30:
            open_percent = 60
        elif avg_snow >= 15:
            open_percent = 40
        else:
            open_percent = max(0, avg_snow * 2)

        # Determine status
        if open_percent >= 90 and fresh > 10:
            status = PisteStatus.EXCELLENT
        elif open_percent >= 70:
            status = PisteStatus.GOOD
        elif open_percent >= 40:
            status = PisteStatus.FAIR
        elif open_percent > 0:
            status = PisteStatus.POOR
        else:
            status = PisteStatus.CLOSED

        # Get artificial snow coverage from resort data
        features = resort.get('features', {})
        snow_cannons_km = features.get('snow_cannons_km', 0)
        artificial_percent = (snow_cannons_km / total_slopes * 100) if total_slopes > 0 else 0

        return PisteCondition(
            status=status,
            open_lifts=int(total_lifts * open_percent / 100),
            total_lifts=total_lifts,
            open_slopes_km=round(total_slopes * open_percent / 100, 1),
            total_slopes_km=total_slopes,
            groomed_percent=min(95, open_percent + 5),
            artificial_snow_percent=min(100, artificial_percent)
        )

    def get_conditions_batch(self, resorts: List[Dict]) -> List[NormalizedSnowCondition]:
        """
        Get conditions for multiple resorts.

        Args:
            resorts: List of resort dictionaries

        Returns:
            List of NormalizedSnowCondition objects
        """
        return [self.get_conditions(resort) for resort in resorts]

    def compare_resorts(self, resorts: List[Dict]) -> Dict:
        """
        Compare snow conditions across multiple resorts.

        Args:
            resorts: List of resort dictionaries

        Returns:
            Dict with comparison data and rankings
        """
        conditions = self.get_conditions_batch(resorts)

        # Sort by overall score
        sorted_conditions = sorted(conditions, key=lambda c: c.overall_score, reverse=True)

        comparison = {
            'ranking': [],
            'best_overall': None,
            'best_snow_depth': None,
            'best_fresh_snow': None,
            'safest': None,
            'updated': datetime.now().isoformat()
        }

        for i, c in enumerate(sorted_conditions):
            comparison['ranking'].append({
                'rank': i + 1,
                'resort': c.resort_name,
                'overall_score': round(c.overall_score, 1),
                'condition_summary': c.condition_summary,
                'snow_quality': c.snow_quality_rating,
                'snow_depth_avg_cm': round(c.snow_depth.average_depth_cm, 0),
                'fresh_snow_7d_cm': round(c.fresh_snow.last_7days_cm, 0),
                'avalanche_risk': c.avalanche.risk_level.value,
                'temperature_c': c.current_temp_c
            })

        if sorted_conditions:
            comparison['best_overall'] = sorted_conditions[0].resort_name
            comparison['best_snow_depth'] = max(conditions,
                key=lambda c: c.snow_depth.average_depth_cm).resort_name
            comparison['best_fresh_snow'] = max(conditions,
                key=lambda c: c.fresh_snow.last_7days_cm).resort_name
            comparison['safest'] = min(conditions,
                key=lambda c: c.avalanche.risk_level.value if c.avalanche.risk_level.value > 0 else 10).resort_name

        return comparison


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_snow_conditions(resort: Dict) -> NormalizedSnowCondition:
    """Get snow conditions for a single resort."""
    aggregator = SnowConditionAggregator()
    return aggregator.get_conditions(resort)


def get_snow_comparison(resorts: List[Dict]) -> Dict:
    """Compare snow conditions across resorts."""
    aggregator = SnowConditionAggregator()
    return aggregator.compare_resorts(resorts)


def format_snow_depth_display(condition: NormalizedSnowCondition) -> str:
    """Format snow depth for display."""
    sd = condition.snow_depth
    return (
        f"Tal ({sd.base_altitude_m}m): {sd.base_depth_cm:.0f}cm | "
        f"Mitte ({sd.mid_altitude_m}m): {sd.mid_depth_cm:.0f}cm | "
        f"Berg ({sd.summit_altitude_m}m): {sd.summit_depth_cm:.0f}cm"
    )


def format_fresh_snow_display(condition: NormalizedSnowCondition) -> str:
    """Format fresh snow data for display."""
    fs = condition.fresh_snow
    return (
        f"24h: {fs.last_24h_cm:.0f}cm | "
        f"48h: {fs.last_48h_cm:.0f}cm | "
        f"7 Tage: {fs.last_7days_cm:.0f}cm"
    )


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    # Test with a sample resort
    test_resort = {
        'name': 'Stubaier Gletscher',
        'lat': 47.0833,
        'lon': 11.3167,
        'altitude_m': 1750,
        'peak_altitude_m': 3210,
        'slopes_km': 65,
        'lifts': 26
    }

    print("Testing Snow Condition Aggregator...")
    print("=" * 50)

    aggregator = SnowConditionAggregator()
    condition = aggregator.get_conditions(test_resort)

    print(f"\nResort: {condition.resort_name}")
    print(f"Overall Score: {condition.overall_score:.1f}/100")
    print(f"Condition: {condition.condition_summary}")
    print(f"Snow Quality: {condition.snow_quality_rating}")
    print(f"\nSnow Depth:")
    print(f"  {format_snow_depth_display(condition)}")
    print(f"\nFresh Snow:")
    print(f"  {format_fresh_snow_display(condition)}")
    print(f"\nAvalanche Risk: {condition.avalanche.risk_level.name}")
    print(f"  {condition.avalanche.risk_description}")
    print(f"\nWeather: {condition.weather_description}")
    print(f"  Temperature: {condition.current_temp_c}°C")
    print(f"  Wind: {condition.wind_speed_kmh} km/h")
    print(f"\nData Sources: {', '.join(condition.data_sources)}")
    print(f"Confidence: {condition.confidence_score:.0%}")
