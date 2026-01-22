"""
Accommodation Search Module
Provides Booking.com integration with smart URL builder and price estimation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, date
from urllib.parse import urlencode, quote
from enum import Enum


class AccommodationType(Enum):
    """Accommodation type categories."""
    HOTEL = "hotel"
    APARTMENT = "apartment"
    CHALET = "chalet"
    HOSTEL = "hostel"
    PENSION = "pension"


class SortOption(Enum):
    """Booking.com sort options."""
    POPULARITY = "popularity"
    PRICE = "price"
    DISTANCE = "distance"
    REVIEW_SCORE = "review_score"
    STARS = "class"


@dataclass
class TravelGroup:
    """Travel group composition for accommodation search."""
    adults: int = 2
    children: int = 0
    child_ages: List[int] = field(default_factory=list)
    rooms: int = 1

    @property
    def total_persons(self) -> int:
        return self.adults + self.children

    def needs_family_room(self) -> bool:
        """Check if family room configuration is needed."""
        return self.children > 0 or self.adults > 2

    def to_booking_params(self) -> Dict:
        """Convert to Booking.com URL parameters."""
        params = {
            'group_adults': self.adults,
            'no_rooms': self.rooms
        }
        if self.children > 0:
            params['group_children'] = self.children
            # Booking.com expects ages as separate params
            if self.child_ages:
                for i, age in enumerate(self.child_ages):
                    params[f'age'] = age  # Multiple age params
        return params

    @classmethod
    def from_dict(cls, data: Dict) -> 'TravelGroup':
        return cls(
            adults=data.get('adults', 2),
            children=data.get('children', 0),
            child_ages=data.get('child_ages', []),
            rooms=data.get('rooms', 1)
        )


@dataclass
class AccommodationPreferences:
    """Search preferences for accommodation."""
    max_price_per_night: Optional[float] = None
    min_rating: float = 7.0  # Booking.com uses 1-10 scale
    max_distance_km: float = 5.0
    accommodation_types: List[AccommodationType] = field(default_factory=list)
    amenities: List[str] = field(default_factory=list)
    ski_in_out: bool = False
    free_cancellation: bool = True
    breakfast_included: bool = False

    # Common amenities codes for Booking.com
    AMENITY_CODES = {
        'wifi': 107,
        'parking': 2,
        'pool': 433,
        'spa': 54,
        'restaurant': 3,
        'ski_storage': 117,
        'sauna': 80,
        'fitness': 11,
        'family_rooms': 28,
        'pets_allowed': 4
    }


@dataclass
class AccommodationResult:
    """Single accommodation search result."""
    name: str
    price_total: float
    price_per_night: float
    currency: str = "EUR"
    rating: float = 0
    review_count: int = 0
    distance_to_center_km: float = 0
    distance_to_slopes_km: float = 0
    accommodation_type: str = ""
    amenities: List[str] = field(default_factory=list)
    booking_url: str = ""
    image_url: str = ""
    address: str = ""

    # Ski-specific
    ski_in_out: bool = False
    ski_bus_stop_m: int = 0

    @property
    def price_display(self) -> str:
        return f"{self.price_total:.0f} {self.currency}"

    @property
    def rating_display(self) -> str:
        if self.rating > 0:
            return f"{self.rating:.1f}/10 ({self.review_count} Bewertungen)"
        return "Keine Bewertung"


@dataclass
class AccommodationSearchResult:
    """Complete search result with multiple accommodations."""
    accommodations: List[AccommodationResult] = field(default_factory=list)
    search_url: str = ""
    total_found: int = 0
    search_params: Dict = field(default_factory=dict)
    price_range: Dict = field(default_factory=dict)
    is_estimate: bool = True


# =============================================================================
# BOOKING.COM URL BUILDER
# =============================================================================

class BookingComUrlBuilder:
    """
    Builds Booking.com search URLs with all parameters.
    Works without API key - generates direct search links.
    """

    BASE_URL = "https://www.booking.com/searchresults.de.html"

    # Resort location IDs (for more accurate searches)
    RESORT_DEST_IDS = {
        'Stubaier Gletscher': '-1980200',
        'Soelden': '-1980219',
        'Ischgl': '-1979888',
        'St. Anton': '-1982147',
        'Kitzbuehel': '-1979913',
        'Zermatt': '-2558260',
        'Chamonix': '-1430881',
        'Cortina d\'Ampezzo': '-117685',
        'Verbier': '-2558177'
    }

    # Country codes for region search
    COUNTRY_CODES = {
        'AT': 'Austria',
        'CH': 'Switzerland',
        'FR': 'France',
        'IT': 'Italy',
        'DE': 'Germany'
    }

    def __init__(self, affiliate_id: Optional[str] = None):
        """
        Initialize URL builder.

        Args:
            affiliate_id: Optional Booking.com affiliate ID for tracking
        """
        self.affiliate_id = affiliate_id

    def build_search_url(
        self,
        resort_name: str,
        checkin: date,
        checkout: date,
        group: TravelGroup,
        preferences: Optional[AccommodationPreferences] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None
    ) -> str:
        """
        Build Booking.com search URL with all parameters.

        Args:
            resort_name: Name of the ski resort
            checkin: Check-in date
            checkout: Check-out date
            group: Travel group composition
            preferences: Search preferences
            lat, lon: Resort coordinates for proximity search

        Returns:
            Complete Booking.com search URL
        """
        params = {}

        # Location search
        dest_id = self.RESORT_DEST_IDS.get(resort_name)
        if dest_id:
            params['dest_id'] = dest_id
            params['dest_type'] = 'city'
        else:
            # Use resort name as search term
            params['ss'] = resort_name

        # If coordinates available, add for proximity
        if lat and lon:
            params['latitude'] = f"{lat:.6f}"
            params['longitude'] = f"{lon:.6f}"

        # Dates
        params['checkin'] = checkin.strftime('%Y-%m-%d')
        params['checkout'] = checkout.strftime('%Y-%m-%d')

        # Group composition
        params['group_adults'] = group.adults
        params['no_rooms'] = group.rooms
        if group.children > 0:
            params['group_children'] = group.children
            # Add child ages
            if group.child_ages:
                for i, age in enumerate(group.child_ages[:group.children]):
                    params[f'age'] = age

        # Preferences
        if preferences:
            self._add_preference_params(params, preferences)

        # Sort by price (most useful for budget comparison)
        params['order'] = 'price'

        # German language
        params['lang'] = 'de'

        # Affiliate tracking
        if self.affiliate_id:
            params['aid'] = self.affiliate_id

        # Selected filters for ski vacation
        params['nflt'] = self._build_filter_string(preferences)

        return f"{self.BASE_URL}?{urlencode(params, doseq=True)}"

    def _add_preference_params(self, params: Dict,
                                preferences: AccommodationPreferences) -> None:
        """Add preference-based parameters to URL."""
        if preferences.max_price_per_night:
            params['price_max'] = int(preferences.max_price_per_night)

        if preferences.min_rating:
            # Booking.com review score filter
            params['review_score'] = int(preferences.min_rating * 10)

    def _build_filter_string(self,
                              preferences: Optional[AccommodationPreferences] = None) -> str:
        """Build the nflt filter string for Booking.com."""
        filters = []

        # Default ski-relevant filters
        filters.append('ht_id=204')  # Hotels
        filters.append('ht_id=201')  # Apartments

        if preferences:
            if preferences.free_cancellation:
                filters.append('fc=2')  # Free cancellation

            if preferences.breakfast_included:
                filters.append('mealplan=1')  # Breakfast included

            if preferences.ski_in_out:
                filters.append('hotelfacility=117')  # Ski storage/equipment

            # Add amenity filters
            for amenity in preferences.amenities:
                code = AccommodationPreferences.AMENITY_CODES.get(amenity.lower())
                if code:
                    filters.append(f'hotelfacility={code}')

        return '%3B'.join(filters)

    def build_map_search_url(
        self,
        lat: float,
        lon: float,
        checkin: date,
        checkout: date,
        group: TravelGroup,
        radius_km: float = 5.0
    ) -> str:
        """
        Build URL for map-based search around coordinates.
        """
        params = {
            'latitude': f"{lat:.6f}",
            'longitude': f"{lon:.6f}",
            'checkin': checkin.strftime('%Y-%m-%d'),
            'checkout': checkout.strftime('%Y-%m-%d'),
            'group_adults': group.adults,
            'no_rooms': group.rooms,
            'lang': 'de',
            'order': 'distance',
            'map': 1
        }

        if group.children > 0:
            params['group_children'] = group.children

        if self.affiliate_id:
            params['aid'] = self.affiliate_id

        return f"{self.BASE_URL}?{urlencode(params)}"


# =============================================================================
# PRICE ESTIMATOR
# =============================================================================

class AccommodationPriceEstimator:
    """
    Estimates accommodation prices based on resort category and season.
    Used as fallback when no API data is available.
    """

    # Base prices per night per room (EUR)
    BASE_PRICES = {
        AccommodationType.HOTEL: {
            'budget': 80,
            'standard': 130,
            'premium': 220
        },
        AccommodationType.APARTMENT: {
            'budget': 100,
            'standard': 160,
            'premium': 280
        },
        AccommodationType.CHALET: {
            'budget': 150,
            'standard': 250,
            'premium': 500
        },
        AccommodationType.HOSTEL: {
            'budget': 35,
            'standard': 50,
            'premium': 70
        },
        AccommodationType.PENSION: {
            'budget': 60,
            'standard': 90,
            'premium': 140
        }
    }

    # Resort category multipliers
    RESORT_CATEGORIES = {
        'luxury': 1.5,      # Zermatt, St. Moritz
        'premium': 1.25,    # Ischgl, Kitzbuehel
        'standard': 1.0,    # Most resorts
        'budget': 0.8       # Smaller resorts
    }

    # Known resort categories
    RESORT_CATEGORY_MAP = {
        'Zermatt': 'luxury',
        'St. Moritz': 'luxury',
        'Verbier': 'luxury',
        'Ischgl': 'premium',
        'Kitzbuehel': 'premium',
        'St. Anton': 'premium',
        'Chamonix': 'premium',
        'Soelden': 'standard',
        'Stubaier Gletscher': 'standard',
        'Cortina d\'Ampezzo': 'premium'
    }

    # Season multipliers
    SEASON_MULTIPLIERS = {
        'peak': 1.4,        # Christmas, New Year, February holidays
        'high': 1.2,        # January, March
        'standard': 1.0,    # Early/Late season
        'low': 0.85         # November, April
    }

    def estimate_price(
        self,
        resort_name: str,
        checkin: date,
        checkout: date,
        group: TravelGroup,
        accommodation_type: AccommodationType = AccommodationType.APARTMENT,
        quality: str = 'standard'
    ) -> Dict:
        """
        Estimate accommodation price for a stay.

        Args:
            resort_name: Name of the ski resort
            checkin, checkout: Stay dates
            group: Travel group
            accommodation_type: Type of accommodation
            quality: 'budget', 'standard', or 'premium'

        Returns:
            Dict with price estimates
        """
        nights = (checkout - checkin).days
        if nights <= 0:
            nights = 1

        # Get base price
        base = self.BASE_PRICES.get(accommodation_type, self.BASE_PRICES[AccommodationType.APARTMENT])
        price_per_night = base.get(quality, base['standard'])

        # Apply resort category multiplier
        resort_category = self.RESORT_CATEGORY_MAP.get(resort_name, 'standard')
        resort_mult = self.RESORT_CATEGORIES.get(resort_category, 1.0)

        # Apply season multiplier
        season = self._determine_season(checkin)
        season_mult = self.SEASON_MULTIPLIERS.get(season, 1.0)

        # Calculate rooms needed
        rooms_needed = self._calculate_rooms_needed(group)

        # Final calculation
        adjusted_price = price_per_night * resort_mult * season_mult
        total_price = adjusted_price * nights * rooms_needed

        return {
            'price_per_night': round(adjusted_price, 0),
            'total_price': round(total_price, 0),
            'nights': nights,
            'rooms': rooms_needed,
            'resort_category': resort_category,
            'season': season,
            'quality': quality,
            'accommodation_type': accommodation_type.value,
            'is_estimate': True,
            'confidence': 0.6,  # 60% confidence for estimates
            'price_range': {
                'min': round(total_price * 0.7, 0),
                'max': round(total_price * 1.3, 0)
            }
        }

    def _determine_season(self, check_date: date) -> str:
        """Determine season based on date."""
        month = check_date.month
        day = check_date.day

        # Peak: Christmas/New Year and February holidays
        if month == 12 and day >= 20:
            return 'peak'
        if month == 1 and day <= 7:
            return 'peak'
        if month == 2 and 10 <= day <= 25:
            return 'peak'

        # High: Most of winter
        if month in [1, 2, 3]:
            return 'high'

        # Low: Shoulder season
        if month in [11, 4]:
            return 'low'

        # Standard: December before Christmas
        return 'standard'

    def _calculate_rooms_needed(self, group: TravelGroup) -> int:
        """Calculate minimum rooms needed for group."""
        # For apartments/chalets, usually 1 unit
        if group.adults <= 2 and group.children <= 2:
            return 1
        # Larger groups need more space
        return max(1, (group.total_persons + 3) // 4)

    def estimate_for_comparison(
        self,
        resort_names: List[str],
        checkin: date,
        checkout: date,
        group: TravelGroup
    ) -> List[Dict]:
        """
        Generate price estimates for multiple resorts for comparison.
        """
        results = []

        for resort in resort_names:
            estimate = self.estimate_price(
                resort,
                checkin,
                checkout,
                group,
                accommodation_type=AccommodationType.APARTMENT,
                quality='standard'
            )
            estimate['resort_name'] = resort
            results.append(estimate)

        # Sort by price
        results.sort(key=lambda x: x['total_price'])

        return results


# =============================================================================
# MAIN SEARCH CLASS
# =============================================================================

class AccommodationSearch:
    """
    Main class for accommodation search functionality.
    Combines URL builder with price estimation.
    """

    def __init__(self, affiliate_id: Optional[str] = None):
        self.url_builder = BookingComUrlBuilder(affiliate_id)
        self.price_estimator = AccommodationPriceEstimator()

    def search(
        self,
        resort: Dict,
        checkin: date,
        checkout: date,
        group: TravelGroup,
        preferences: Optional[AccommodationPreferences] = None
    ) -> AccommodationSearchResult:
        """
        Search for accommodations near a resort.

        Args:
            resort: Resort dict with name, lat, lon
            checkin, checkout: Stay dates
            group: Travel group
            preferences: Search preferences

        Returns:
            AccommodationSearchResult with booking URL and price estimates
        """
        resort_name = resort.get('name', '')
        lat = resort.get('lat')
        lon = resort.get('lon')

        # Build booking URL
        search_url = self.url_builder.build_search_url(
            resort_name=resort_name,
            checkin=checkin,
            checkout=checkout,
            group=group,
            preferences=preferences,
            lat=lat,
            lon=lon
        )

        # Generate price estimates
        budget_estimate = self.price_estimator.estimate_price(
            resort_name, checkin, checkout, group,
            AccommodationType.HOSTEL, 'budget'
        )
        standard_estimate = self.price_estimator.estimate_price(
            resort_name, checkin, checkout, group,
            AccommodationType.APARTMENT, 'standard'
        )
        premium_estimate = self.price_estimator.estimate_price(
            resort_name, checkin, checkout, group,
            AccommodationType.HOTEL, 'premium'
        )

        # Create sample results based on estimates
        accommodations = [
            AccommodationResult(
                name=f"Budget Unterkunft nahe {resort_name}",
                price_total=budget_estimate['total_price'],
                price_per_night=budget_estimate['price_per_night'],
                accommodation_type='hostel/pension',
                rating=7.5,
                distance_to_slopes_km=2.0,
                booking_url=search_url
            ),
            AccommodationResult(
                name=f"Ferienwohnung {resort_name}",
                price_total=standard_estimate['total_price'],
                price_per_night=standard_estimate['price_per_night'],
                accommodation_type='apartment',
                rating=8.2,
                distance_to_slopes_km=0.5,
                booking_url=search_url
            ),
            AccommodationResult(
                name=f"Hotel {resort_name}",
                price_total=premium_estimate['total_price'],
                price_per_night=premium_estimate['price_per_night'],
                accommodation_type='hotel',
                rating=8.8,
                distance_to_slopes_km=0.2,
                ski_in_out=True,
                booking_url=search_url
            )
        ]

        return AccommodationSearchResult(
            accommodations=accommodations,
            search_url=search_url,
            total_found=3,
            search_params={
                'resort': resort_name,
                'checkin': checkin.isoformat(),
                'checkout': checkout.isoformat(),
                'nights': (checkout - checkin).days,
                'adults': group.adults,
                'children': group.children,
                'rooms': group.rooms
            },
            price_range={
                'min': budget_estimate['total_price'],
                'max': premium_estimate['total_price'],
                'average': standard_estimate['total_price']
            },
            is_estimate=True
        )

    def compare_resorts(
        self,
        resorts: List[Dict],
        checkin: date,
        checkout: date,
        group: TravelGroup
    ) -> Dict:
        """
        Compare accommodation prices across multiple resorts.

        Returns:
            Dict with comparison data
        """
        results = []

        for resort in resorts:
            search_result = self.search(resort, checkin, checkout, group)

            results.append({
                'resort_name': resort.get('name', ''),
                'budget_price': search_result.price_range['min'],
                'standard_price': search_result.price_range['average'],
                'premium_price': search_result.price_range['max'],
                'booking_url': search_result.search_url,
                'is_estimate': True
            })

        # Sort by standard price
        results.sort(key=lambda x: x['standard_price'])

        # Find cheapest
        cheapest = results[0] if results else None

        return {
            'comparison': results,
            'cheapest_resort': cheapest['resort_name'] if cheapest else None,
            'price_difference': (
                results[-1]['standard_price'] - results[0]['standard_price']
                if len(results) > 1 else 0
            ),
            'nights': (checkout - checkin).days,
            'group_size': group.total_persons
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_accommodation_url(
    resort_name: str,
    checkin: date,
    checkout: date,
    adults: int = 2,
    children: int = 0,
    rooms: int = 1
) -> str:
    """
    Quick function to get Booking.com search URL.
    """
    builder = BookingComUrlBuilder()
    group = TravelGroup(adults=adults, children=children, rooms=rooms)

    return builder.build_search_url(
        resort_name=resort_name,
        checkin=checkin,
        checkout=checkout,
        group=group
    )


def estimate_accommodation_cost(
    resort_name: str,
    nights: int,
    adults: int = 2,
    children: int = 0,
    quality: str = 'standard'
) -> Dict:
    """
    Quick function to estimate accommodation cost.
    """
    from datetime import timedelta

    checkin = date.today() + timedelta(days=30)
    checkout = checkin + timedelta(days=nights)

    estimator = AccommodationPriceEstimator()
    group = TravelGroup(adults=adults, children=children)

    return estimator.estimate_price(
        resort_name,
        checkin,
        checkout,
        group,
        AccommodationType.APARTMENT,
        quality
    )


def format_price_display(price: float, currency: str = "EUR") -> str:
    """Format price for display."""
    return f"{price:,.0f} {currency}".replace(",", ".")


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    from datetime import timedelta

    # Test accommodation search
    print("Testing Accommodation Search...")
    print("=" * 50)

    resort = {
        'name': 'Stubaier Gletscher',
        'lat': 47.0833,
        'lon': 11.3167
    }

    checkin = date.today() + timedelta(days=60)
    checkout = checkin + timedelta(days=7)

    group = TravelGroup(adults=2, children=2, child_ages=[8, 12], rooms=1)

    search = AccommodationSearch()
    result = search.search(resort, checkin, checkout, group)

    print(f"\nSuche fuer: {resort['name']}")
    print(f"Zeitraum: {checkin} - {checkout} ({(checkout-checkin).days} Naechte)")
    print(f"Reisegruppe: {group.adults} Erwachsene, {group.children} Kinder")
    print(f"\nBooking.com URL:")
    print(result.search_url[:100] + "...")
    print(f"\nPreisschaetzungen:")
    print(f"  Budget: {format_price_display(result.price_range['min'])}")
    print(f"  Standard: {format_price_display(result.price_range['average'])}")
    print(f"  Premium: {format_price_display(result.price_range['max'])}")

    # Test comparison
    print("\n" + "=" * 50)
    print("Resort-Vergleich...")

    resorts = [
        {'name': 'Stubaier Gletscher', 'lat': 47.08, 'lon': 11.31},
        {'name': 'Ischgl', 'lat': 46.97, 'lon': 10.29},
        {'name': 'Zermatt', 'lat': 46.02, 'lon': 7.75}
    ]

    comparison = search.compare_resorts(resorts, checkin, checkout, group)

    print(f"\nGuenstigstes Resort: {comparison['cheapest_resort']}")
    print(f"Preisdifferenz: {format_price_display(comparison['price_difference'])}")
    print("\nAlle Resorts:")
    for r in comparison['comparison']:
        print(f"  {r['resort_name']}: {format_price_display(r['standard_price'])}")
