"""
Snow Conditions Data Models
Normalized data structures for comparable snow conditions across resorts.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class AvalancheRisk(Enum):
    """European Avalanche Danger Scale (1-5)."""
    LOW = 1           # Gering
    MODERATE = 2      # Maessig
    CONSIDERABLE = 3  # Erheblich
    HIGH = 4          # Gross
    VERY_HIGH = 5     # Sehr gross
    UNKNOWN = 0       # Keine Daten


class PisteStatus(Enum):
    """Piste condition status."""
    EXCELLENT = "excellent"      # Bestens praepariert
    GOOD = "good"               # Gut praepariert
    FAIR = "fair"               # Akzeptabel
    POOR = "poor"               # Schlecht
    CLOSED = "closed"           # Geschlossen
    UNKNOWN = "unknown"


@dataclass
class SnowDepthData:
    """
    Snow depth measurements at different altitudes.
    All values in centimeters.
    """
    base_depth_cm: float = 0       # Schnehoehe Tal
    mid_depth_cm: float = 0        # Schnehoehe Mitte
    summit_depth_cm: float = 0     # Schnehoehe Berg

    # Altitude references (meters)
    base_altitude_m: int = 0
    mid_altitude_m: int = 0
    summit_altitude_m: int = 0

    measurement_time: Optional[datetime] = None

    @property
    def average_depth_cm(self) -> float:
        """Calculate average snow depth across all stations."""
        depths = [d for d in [self.base_depth_cm, self.mid_depth_cm, self.summit_depth_cm] if d > 0]
        return sum(depths) / len(depths) if depths else 0

    @property
    def snow_gradient(self) -> float:
        """
        Snow depth increase per 100m altitude.
        Higher values indicate more snow at altitude.
        """
        if self.summit_altitude_m <= self.base_altitude_m:
            return 0
        altitude_diff = (self.summit_altitude_m - self.base_altitude_m) / 100
        snow_diff = self.summit_depth_cm - self.base_depth_cm
        return snow_diff / altitude_diff if altitude_diff > 0 else 0

    def to_dict(self) -> Dict:
        return {
            'base_depth_cm': self.base_depth_cm,
            'mid_depth_cm': self.mid_depth_cm,
            'summit_depth_cm': self.summit_depth_cm,
            'base_altitude_m': self.base_altitude_m,
            'mid_altitude_m': self.mid_altitude_m,
            'summit_altitude_m': self.summit_altitude_m,
            'average_depth_cm': round(self.average_depth_cm, 1),
            'snow_gradient': round(self.snow_gradient, 2),
            'measurement_time': self.measurement_time.isoformat() if self.measurement_time else None
        }


@dataclass
class FreshSnowData:
    """
    Fresh snowfall measurements over different time periods.
    All values in centimeters.
    """
    last_24h_cm: float = 0
    last_48h_cm: float = 0
    last_72h_cm: float = 0
    last_7days_cm: float = 0

    # Forecast
    next_24h_cm: float = 0
    next_48h_cm: float = 0
    next_7days_cm: float = 0

    last_snowfall_date: Optional[datetime] = None

    @property
    def is_fresh_snow(self) -> bool:
        """Check if there was recent snowfall (last 48h)."""
        return self.last_48h_cm > 5

    @property
    def snowfall_trend(self) -> str:
        """Determine snowfall trend."""
        if self.next_48h_cm > 20:
            return "heavy_snow_expected"
        elif self.next_48h_cm > 5:
            return "snow_expected"
        elif self.last_48h_cm > 20:
            return "recent_heavy_snow"
        elif self.last_48h_cm > 5:
            return "recent_snow"
        else:
            return "stable"

    def to_dict(self) -> Dict:
        return {
            'last_24h_cm': self.last_24h_cm,
            'last_48h_cm': self.last_48h_cm,
            'last_72h_cm': self.last_72h_cm,
            'last_7days_cm': self.last_7days_cm,
            'next_24h_cm': self.next_24h_cm,
            'next_48h_cm': self.next_48h_cm,
            'next_7days_cm': self.next_7days_cm,
            'is_fresh_snow': self.is_fresh_snow,
            'snowfall_trend': self.snowfall_trend,
            'last_snowfall_date': self.last_snowfall_date.isoformat() if self.last_snowfall_date else None
        }


@dataclass
class AvalancheData:
    """
    Avalanche risk and safety information.
    Based on European Avalanche Danger Scale.
    """
    risk_level: AvalancheRisk = AvalancheRisk.UNKNOWN
    risk_description: str = ""

    # Elevation-specific risks
    risk_below_treeline: Optional[int] = None    # Below ~1800m
    risk_above_treeline: Optional[int] = None    # Above treeline
    risk_alpine: Optional[int] = None            # High alpine >2500m

    # Problem types
    problem_types: List[str] = field(default_factory=list)
    # Common: "fresh_snow", "wind_slab", "persistent_weak_layer", "wet_snow", "glide_snow"

    danger_aspects: List[str] = field(default_factory=list)  # N, NE, E, SE, S, SW, W, NW
    danger_elevations: str = ""  # e.g., "above 2000m"

    valid_until: Optional[datetime] = None
    bulletin_url: str = ""

    @property
    def is_safe_for_piste(self) -> bool:
        """Check if conditions are generally safe for on-piste skiing."""
        return self.risk_level.value <= 3

    @property
    def freeride_warning(self) -> bool:
        """Check if freeriding should be avoided."""
        return self.risk_level.value >= 3

    def to_dict(self) -> Dict:
        return {
            'risk_level': self.risk_level.value,
            'risk_level_name': self.risk_level.name,
            'risk_description': self.risk_description,
            'risk_below_treeline': self.risk_below_treeline,
            'risk_above_treeline': self.risk_above_treeline,
            'risk_alpine': self.risk_alpine,
            'problem_types': self.problem_types,
            'danger_aspects': self.danger_aspects,
            'danger_elevations': self.danger_elevations,
            'is_safe_for_piste': self.is_safe_for_piste,
            'freeride_warning': self.freeride_warning,
            'valid_until': self.valid_until.isoformat() if self.valid_until else None,
            'bulletin_url': self.bulletin_url
        }


@dataclass
class PisteCondition:
    """
    Detailed piste condition information.
    """
    status: PisteStatus = PisteStatus.UNKNOWN
    open_lifts: int = 0
    total_lifts: int = 0
    open_slopes_km: float = 0
    total_slopes_km: float = 0

    # Conditions
    groomed_percent: float = 0      # Percentage of groomed slopes
    artificial_snow_percent: float = 0  # Artificial snow coverage

    last_grooming: Optional[datetime] = None

    @property
    def lift_availability(self) -> float:
        """Percentage of lifts open."""
        return (self.open_lifts / self.total_lifts * 100) if self.total_lifts > 0 else 0

    @property
    def slope_availability(self) -> float:
        """Percentage of slopes open."""
        return (self.open_slopes_km / self.total_slopes_km * 100) if self.total_slopes_km > 0 else 0

    def to_dict(self) -> Dict:
        return {
            'status': self.status.value,
            'open_lifts': self.open_lifts,
            'total_lifts': self.total_lifts,
            'open_slopes_km': self.open_slopes_km,
            'total_slopes_km': self.total_slopes_km,
            'lift_availability': round(self.lift_availability, 1),
            'slope_availability': round(self.slope_availability, 1),
            'groomed_percent': self.groomed_percent,
            'artificial_snow_percent': self.artificial_snow_percent,
            'last_grooming': self.last_grooming.isoformat() if self.last_grooming else None
        }


@dataclass
class NormalizedSnowCondition:
    """
    Complete normalized snow condition for a resort.
    Combines all data sources into comparable metrics.
    """
    resort_name: str
    resort_id: str = ""

    # Core data
    snow_depth: SnowDepthData = field(default_factory=SnowDepthData)
    fresh_snow: FreshSnowData = field(default_factory=FreshSnowData)
    avalanche: AvalancheData = field(default_factory=AvalancheData)
    piste: PisteCondition = field(default_factory=PisteCondition)

    # Weather context
    current_temp_c: float = 0
    freezing_level_m: int = 0
    wind_speed_kmh: float = 0
    visibility_km: float = 10
    weather_description: str = ""

    # Data quality
    confidence_score: float = 0.5  # 0-1, how reliable is the data
    data_sources: List[str] = field(default_factory=list)
    last_updated: Optional[datetime] = None

    # Cache info
    cache_expires: Optional[datetime] = None

    @property
    def overall_score(self) -> float:
        """
        Calculate overall snow condition score (0-100).
        Weighted combination of all factors.
        """
        score = 0

        # Snow depth (35 points max)
        avg_depth = self.snow_depth.average_depth_cm
        if avg_depth >= 150:
            score += 35
        elif avg_depth >= 80:
            score += 30
        elif avg_depth >= 50:
            score += 25
        elif avg_depth >= 30:
            score += 15
        elif avg_depth > 0:
            score += 5

        # Fresh snow (25 points max)
        fresh = self.fresh_snow.last_7days_cm
        if fresh >= 50:
            score += 25
        elif fresh >= 30:
            score += 20
        elif fresh >= 15:
            score += 15
        elif fresh >= 5:
            score += 10
        elif fresh > 0:
            score += 5

        # Piste availability (20 points max)
        availability = self.piste.slope_availability
        score += (availability / 100) * 20

        # Safety (10 points max)
        if self.avalanche.risk_level.value <= 2:
            score += 10
        elif self.avalanche.risk_level.value == 3:
            score += 5
        # Higher risk = 0 bonus

        # Weather (10 points max)
        if -10 <= self.current_temp_c <= 0:
            score += 5  # Ideal skiing temperature
        elif -15 <= self.current_temp_c <= 5:
            score += 3

        if self.visibility_km >= 10:
            score += 5
        elif self.visibility_km >= 5:
            score += 3

        return min(100, score)

    @property
    def condition_summary(self) -> str:
        """Generate human-readable condition summary."""
        score = self.overall_score

        if score >= 80:
            return "Ausgezeichnete Bedingungen"
        elif score >= 60:
            return "Gute Bedingungen"
        elif score >= 40:
            return "Akzeptable Bedingungen"
        elif score >= 20:
            return "Eingeschraenkte Bedingungen"
        else:
            return "Schlechte Bedingungen"

    @property
    def snow_quality_rating(self) -> str:
        """Rate snow quality based on conditions."""
        temp = self.current_temp_c
        fresh = self.fresh_snow.last_48h_cm

        if fresh > 20 and temp < -5:
            return "Powder"
        elif fresh > 10 and temp < 0:
            return "Frischer Schnee"
        elif temp < -3:
            return "Hart/Griffig"
        elif temp < 2:
            return "Gut befahrbar"
        else:
            return "Sulzig/Weich"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'resort_name': self.resort_name,
            'resort_id': self.resort_id,
            'snow_depth': self.snow_depth.to_dict(),
            'fresh_snow': self.fresh_snow.to_dict(),
            'avalanche': self.avalanche.to_dict(),
            'piste': self.piste.to_dict(),
            'current_temp_c': self.current_temp_c,
            'freezing_level_m': self.freezing_level_m,
            'wind_speed_kmh': self.wind_speed_kmh,
            'visibility_km': self.visibility_km,
            'weather_description': self.weather_description,
            'overall_score': round(self.overall_score, 1),
            'condition_summary': self.condition_summary,
            'snow_quality_rating': self.snow_quality_rating,
            'confidence_score': self.confidence_score,
            'data_sources': self.data_sources,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'NormalizedSnowCondition':
        """Create instance from dictionary."""
        condition = cls(
            resort_name=data.get('resort_name', ''),
            resort_id=data.get('resort_id', ''),
            current_temp_c=data.get('current_temp_c', 0),
            freezing_level_m=data.get('freezing_level_m', 0),
            wind_speed_kmh=data.get('wind_speed_kmh', 0),
            visibility_km=data.get('visibility_km', 10),
            weather_description=data.get('weather_description', ''),
            confidence_score=data.get('confidence_score', 0.5),
            data_sources=data.get('data_sources', [])
        )

        # Parse nested structures
        if 'snow_depth' in data:
            sd = data['snow_depth']
            condition.snow_depth = SnowDepthData(
                base_depth_cm=sd.get('base_depth_cm', 0),
                mid_depth_cm=sd.get('mid_depth_cm', 0),
                summit_depth_cm=sd.get('summit_depth_cm', 0),
                base_altitude_m=sd.get('base_altitude_m', 0),
                mid_altitude_m=sd.get('mid_altitude_m', 0),
                summit_altitude_m=sd.get('summit_altitude_m', 0)
            )

        if 'fresh_snow' in data:
            fs = data['fresh_snow']
            condition.fresh_snow = FreshSnowData(
                last_24h_cm=fs.get('last_24h_cm', 0),
                last_48h_cm=fs.get('last_48h_cm', 0),
                last_72h_cm=fs.get('last_72h_cm', 0),
                last_7days_cm=fs.get('last_7days_cm', 0),
                next_24h_cm=fs.get('next_24h_cm', 0),
                next_48h_cm=fs.get('next_48h_cm', 0),
                next_7days_cm=fs.get('next_7days_cm', 0)
            )

        if 'avalanche' in data:
            av = data['avalanche']
            risk_val = av.get('risk_level', 0)
            condition.avalanche = AvalancheData(
                risk_level=AvalancheRisk(risk_val) if isinstance(risk_val, int) else AvalancheRisk.UNKNOWN,
                risk_description=av.get('risk_description', ''),
                problem_types=av.get('problem_types', []),
                danger_aspects=av.get('danger_aspects', []),
                danger_elevations=av.get('danger_elevations', ''),
                bulletin_url=av.get('bulletin_url', '')
            )

        if 'piste' in data:
            pi = data['piste']
            status_val = pi.get('status', 'unknown')
            condition.piste = PisteCondition(
                status=PisteStatus(status_val) if status_val in [s.value for s in PisteStatus] else PisteStatus.UNKNOWN,
                open_lifts=pi.get('open_lifts', 0),
                total_lifts=pi.get('total_lifts', 0),
                open_slopes_km=pi.get('open_slopes_km', 0),
                total_slopes_km=pi.get('total_slopes_km', 0),
                groomed_percent=pi.get('groomed_percent', 0),
                artificial_snow_percent=pi.get('artificial_snow_percent', 0)
            )

        return condition


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_avalanche_risk_label(risk: AvalancheRisk) -> str:
    """Get German label for avalanche risk level."""
    labels = {
        AvalancheRisk.LOW: "Gering (1)",
        AvalancheRisk.MODERATE: "Maessig (2)",
        AvalancheRisk.CONSIDERABLE: "Erheblich (3)",
        AvalancheRisk.HIGH: "Gross (4)",
        AvalancheRisk.VERY_HIGH: "Sehr gross (5)",
        AvalancheRisk.UNKNOWN: "Keine Daten"
    }
    return labels.get(risk, "Unbekannt")


def get_avalanche_risk_color(risk: AvalancheRisk) -> str:
    """Get color code for avalanche risk level."""
    colors = {
        AvalancheRisk.LOW: "#00FF00",         # Green
        AvalancheRisk.MODERATE: "#FFFF00",    # Yellow
        AvalancheRisk.CONSIDERABLE: "#FFA500", # Orange
        AvalancheRisk.HIGH: "#FF0000",        # Red
        AvalancheRisk.VERY_HIGH: "#000000",   # Black
        AvalancheRisk.UNKNOWN: "#808080"      # Gray
    }
    return colors.get(risk, "#808080")


def get_piste_status_label(status: PisteStatus) -> str:
    """Get German label for piste status."""
    labels = {
        PisteStatus.EXCELLENT: "Bestens praepariert",
        PisteStatus.GOOD: "Gut praepariert",
        PisteStatus.FAIR: "Akzeptabel",
        PisteStatus.POOR: "Schlecht",
        PisteStatus.CLOSED: "Geschlossen",
        PisteStatus.UNKNOWN: "Keine Daten"
    }
    return labels.get(status, "Unbekannt")


def compare_snow_conditions(conditions: List[NormalizedSnowCondition]) -> Dict:
    """
    Compare snow conditions across multiple resorts.
    Returns ranking and comparison data.
    """
    if not conditions:
        return {}

    # Sort by overall score
    sorted_conditions = sorted(conditions, key=lambda c: c.overall_score, reverse=True)

    comparison = {
        'ranking': [
            {
                'rank': i + 1,
                'resort': c.resort_name,
                'score': round(c.overall_score, 1),
                'summary': c.condition_summary,
                'snow_depth_avg': round(c.snow_depth.average_depth_cm, 0),
                'fresh_snow_7d': c.fresh_snow.last_7days_cm,
                'avalanche_risk': c.avalanche.risk_level.value
            }
            for i, c in enumerate(sorted_conditions)
        ],
        'best_snow_depth': max(conditions, key=lambda c: c.snow_depth.average_depth_cm).resort_name,
        'best_fresh_snow': max(conditions, key=lambda c: c.fresh_snow.last_7days_cm).resort_name,
        'safest': min(conditions, key=lambda c: c.avalanche.risk_level.value).resort_name,
        'best_availability': max(conditions, key=lambda c: c.piste.slope_availability).resort_name
    }

    return comparison


def estimate_snow_depth_at_altitude(base_depth: float, base_alt: int,
                                     target_alt: int, gradient: float = 3.0) -> float:
    """
    Estimate snow depth at a given altitude.
    Default gradient: 3cm per 100m altitude increase.
    """
    alt_diff = (target_alt - base_alt) / 100
    return max(0, base_depth + (alt_diff * gradient))
