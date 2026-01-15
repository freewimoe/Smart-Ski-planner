"""
Travel Budget Calculator for Ski Vacation Planner
Calculates total trip costs including transport, accommodation, ski passes, and extras.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import math


class TransportMode(Enum):
    """Available transport modes."""
    CAR = "car"
    TRAIN = "train"
    BUS = "bus"
    FLIGHT = "flight"


@dataclass
class TravelParty:
    """Travel party composition."""
    adults: int = 2
    children: int = 0
    child_ages: List[int] = field(default_factory=list)

    @property
    def total_persons(self) -> int:
        return self.adults + self.children

    def children_needing_ticket(self, min_age: int = 6) -> int:
        """Count children above minimum age who need tickets."""
        if not self.child_ages:
            # If no ages specified, assume all children need tickets
            return self.children
        return sum(1 for age in self.child_ages if age >= min_age)

    @classmethod
    def from_dict(cls, data: Dict) -> 'TravelParty':
        return cls(
            adults=data.get('adults', 2),
            children=data.get('children', 0),
            child_ages=data.get('child_ages', [])
        )


@dataclass
class TripDetails:
    """Trip duration and distance details."""
    nights: int = 7
    ski_days: int = 6  # Typically 1 rest day
    distance_km: float = 400

    @classmethod
    def from_dates(cls, start_date, end_date, distance_km: float) -> 'TripDetails':
        nights = (end_date - start_date).days
        return cls(
            nights=nights,
            ski_days=max(1, nights - 1),
            distance_km=distance_km
        )


@dataclass
class BudgetOptions:
    """Optional extras for the vacation."""
    rent_equipment: bool = True
    ski_school_adults: bool = False
    ski_school_children: bool = True
    half_board: bool = True
    ski_insurance: bool = True
    accommodation_type: str = 'hotel'  # hotel, apartment, hostel

    @classmethod
    def from_dict(cls, data: Dict) -> 'BudgetOptions':
        return cls(
            rent_equipment=data.get('rent_equipment', True),
            ski_school_adults=data.get('ski_school_adults', False),
            ski_school_children=data.get('ski_school_children', True),
            half_board=data.get('half_board', True),
            ski_insurance=data.get('ski_insurance', True),
            accommodation_type=data.get('accommodation_type', 'hotel')
        )


@dataclass
class BudgetBreakdown:
    """Detailed cost breakdown."""
    accommodation: float = 0
    ski_passes: float = 0
    transport: float = 0
    equipment_rental: float = 0
    ski_school: float = 0
    meals: float = 0
    insurance: float = 0
    extras: float = 0

    @property
    def total(self) -> float:
        return sum([
            self.accommodation,
            self.ski_passes,
            self.transport,
            self.equipment_rental,
            self.ski_school,
            self.meals,
            self.insurance,
            self.extras
        ])

    def to_dict(self) -> Dict[str, float]:
        return {
            'Unterkunft': self.accommodation,
            'Skipaesse': self.ski_passes,
            'Anreise': self.transport,
            'Ausruestung': self.equipment_rental,
            'Skischule': self.ski_school,
            'Verpflegung': self.meals,
            'Versicherung': self.insurance,
            'Sonstiges': self.extras
        }

    def per_person(self, num_persons: int) -> float:
        return self.total / num_persons if num_persons > 0 else self.total


class BudgetCalculator:
    """
    Calculates detailed vacation costs.
    """

    # Default prices (can be overridden with resort-specific prices)
    DEFAULT_PRICES = {
        'hotel_per_night_pp': 85,        # Per person per night
        'apartment_per_night': 160,       # Entire unit per night
        'hostel_per_night_pp': 40,
        'skipass_day_adult': 58,
        'skipass_day_child': 32,
        'skipass_week_adult': 290,
        'skipass_week_child': 160,
        'equipment_day_adult': 38,
        'equipment_day_child': 22,
        'ski_school_day': 65,
        'meal_breakfast': 15,
        'meal_lunch': 22,
        'meal_dinner': 38,
        'insurance_day_pp': 5,
    }

    # Transport costs
    TRANSPORT_COSTS = {
        TransportMode.CAR: {
            'per_km': 0.32,           # Fuel + wear
            'toll_per_100km': 6,      # Average toll
            'parking_per_day': 15
        },
        TransportMode.TRAIN: {
            'base_price': 55,
            'per_100km': 18,
            'discount_group': 0.25    # Group discount
        },
        TransportMode.BUS: {
            'base_price': 35,
            'per_100km': 10
        },
        TransportMode.FLIGHT: {
            'base_price_pp': 160,
            'transfer_to_resort': 90
        }
    }

    def __init__(self, resort_prices: Optional[Dict] = None):
        """
        Initialize calculator with optional resort-specific prices.

        Args:
            resort_prices: Override default prices with resort-specific values
        """
        self.prices = {**self.DEFAULT_PRICES}
        if resort_prices:
            self.prices.update(resort_prices)

    def calculate_accommodation(self, party: TravelParty, trip: TripDetails,
                                accommodation_type: str = 'hotel') -> float:
        """Calculate accommodation costs."""
        if accommodation_type == 'hotel':
            adult_cost = party.adults * trip.nights * self.prices['hotel_per_night_pp']
            # Children usually 50% price
            child_cost = party.children * trip.nights * self.prices['hotel_per_night_pp'] * 0.5
            return adult_cost + child_cost

        elif accommodation_type == 'apartment':
            base = self.prices['apartment_per_night'] * trip.nights
            # Surcharge for larger groups
            if party.total_persons > 4:
                base *= 1.35
            elif party.total_persons > 2:
                base *= 1.15
            return base

        else:  # hostel
            return party.total_persons * trip.nights * self.prices['hostel_per_night_pp']

    def calculate_ski_passes(self, party: TravelParty, trip: TripDetails,
                            pass_type: str = 'auto') -> float:
        """
        Calculate ski pass costs.

        Args:
            pass_type: 'day', 'week', 'auto' (chooses cheapest)
        """
        ski_days = trip.ski_days

        # Day passes
        day_adult = self.prices['skipass_day_adult']
        day_child = self.prices['skipass_day_child']
        daily_total = (party.adults * day_adult + party.children * day_child) * ski_days

        # Week passes (often cheaper for 5+ days)
        week_adult = self.prices['skipass_week_adult']
        week_child = self.prices['skipass_week_child']
        weekly_total = party.adults * week_adult + party.children * week_child

        if pass_type == 'day':
            return daily_total
        elif pass_type == 'week':
            return weekly_total
        else:  # auto
            return min(daily_total, weekly_total)

    def calculate_transport(self, party: TravelParty, trip: TripDetails,
                           mode: TransportMode) -> Dict[str, float]:
        """
        Calculate transport costs with breakdown.

        Returns:
            Dict with cost breakdown and total
        """
        distance = trip.distance_km
        costs = self.TRANSPORT_COSTS[mode]

        if mode == TransportMode.CAR:
            # Round trip
            fuel_cost = distance * 2 * costs['per_km']
            toll = (distance / 100) * 2 * costs['toll_per_100km']
            parking = trip.nights * costs['parking_per_day']

            return {
                'Benzin': round(fuel_cost, 2),
                'Maut': round(toll, 2),
                'Parken': round(parking, 2),
                'total': round(fuel_cost + toll + parking, 2)
            }

        elif mode == TransportMode.TRAIN:
            base = costs['base_price']
            distance_cost = (distance / 100) * costs['per_100km']
            per_person = base + distance_cost

            # Group discount for 4+ persons
            total_persons = party.total_persons
            if total_persons >= 4:
                per_person *= (1 - costs['discount_group'])

            roundtrip = per_person * total_persons * 2

            return {
                'Bahntickets': round(roundtrip, 2),
                'total': round(roundtrip, 2)
            }

        elif mode == TransportMode.BUS:
            base = costs['base_price']
            distance_cost = (distance / 100) * costs['per_100km']
            per_person = base + distance_cost
            roundtrip = per_person * party.total_persons * 2

            return {
                'Bustickets': round(roundtrip, 2),
                'total': round(roundtrip, 2)
            }

        elif mode == TransportMode.FLIGHT:
            flight_pp = costs['base_price_pp']
            flights = flight_pp * party.total_persons * 2
            transfer = costs['transfer_to_resort'] * 2

            return {
                'Fluege': round(flights, 2),
                'Transfer': round(transfer, 2),
                'total': round(flights + transfer, 2)
            }

        return {'total': 0}

    def calculate_equipment(self, party: TravelParty, trip: TripDetails,
                           rent_equipment: bool = True) -> float:
        """Calculate equipment rental costs."""
        if not rent_equipment:
            return 0

        adult_cost = party.adults * trip.ski_days * self.prices['equipment_day_adult']
        child_cost = party.children * trip.ski_days * self.prices['equipment_day_child']

        return adult_cost + child_cost

    def calculate_ski_school(self, party: TravelParty, trip: TripDetails,
                            options: BudgetOptions) -> float:
        """Calculate ski school costs."""
        cost = 0
        school_days = min(3, trip.ski_days)  # Typically max 3 days

        if options.ski_school_children and party.children > 0:
            cost += party.children * school_days * self.prices['ski_school_day']

        if options.ski_school_adults:
            cost += party.adults * school_days * self.prices['ski_school_day']

        return cost

    def calculate_meals(self, party: TravelParty, trip: TripDetails,
                       options: BudgetOptions) -> float:
        """
        Calculate meal costs.
        With half-board, only lunch needs to be paid extra.
        """
        if options.half_board:
            # Only lunch on the slopes
            lunch_cost = party.total_persons * trip.ski_days * self.prices['meal_lunch']
            return lunch_cost
        else:
            # All meals
            daily_pp = (self.prices['meal_breakfast'] +
                       self.prices['meal_lunch'] +
                       self.prices['meal_dinner'])
            return party.total_persons * trip.nights * daily_pp

    def calculate_insurance(self, party: TravelParty, trip: TripDetails,
                           options: BudgetOptions) -> float:
        """Calculate travel/ski insurance costs."""
        if not options.ski_insurance:
            return 0

        return party.total_persons * trip.nights * self.prices['insurance_day_pp']

    def calculate_full_budget(self, party: TravelParty, trip: TripDetails,
                             options: BudgetOptions,
                             transport_mode: TransportMode = TransportMode.CAR) -> BudgetBreakdown:
        """
        Calculate complete trip budget.
        """
        transport_details = self.calculate_transport(party, trip, transport_mode)

        breakdown = BudgetBreakdown(
            accommodation=self.calculate_accommodation(party, trip, options.accommodation_type),
            ski_passes=self.calculate_ski_passes(party, trip),
            transport=transport_details['total'],
            equipment_rental=self.calculate_equipment(party, trip, options.rent_equipment),
            ski_school=self.calculate_ski_school(party, trip, options),
            meals=self.calculate_meals(party, trip, options),
            insurance=self.calculate_insurance(party, trip, options),
            extras=50 * party.total_persons  # Flat rate for misc
        )

        return breakdown

    def compare_transport_modes(self, party: TravelParty,
                                trip: TripDetails) -> Dict[str, float]:
        """
        Compare costs of different transport modes.
        """
        comparison = {}
        for mode in TransportMode:
            details = self.calculate_transport(party, trip, mode)
            comparison[mode.value] = details['total']

        return comparison

    def get_savings_tips(self, breakdown: BudgetBreakdown,
                        party: TravelParty, trip: TripDetails) -> List[str]:
        """Generate savings tips based on the budget."""
        tips = []

        # Check if week pass would be cheaper
        daily_pass_cost = (self.prices['skipass_day_adult'] * party.adults +
                          self.prices['skipass_day_child'] * party.children) * trip.ski_days
        week_pass_cost = (self.prices['skipass_week_adult'] * party.adults +
                         self.prices['skipass_week_child'] * party.children)

        if daily_pass_cost < week_pass_cost and breakdown.ski_passes == week_pass_cost:
            savings = week_pass_cost - daily_pass_cost
            tips.append(f"Tageskarten statt Wochenkarten sparen {savings:.0f} EUR")

        # Equipment rental tip
        if breakdown.equipment_rental > 0:
            own_equipment_threshold = breakdown.equipment_rental * 3
            tips.append(f"Eigene Ausruestung lohnt sich ab ca. {own_equipment_threshold:.0f} EUR")

        # Accommodation tip
        if breakdown.accommodation > party.total_persons * trip.nights * 60:
            tips.append("Ferienwohnung mit Selbstverpflegung kann guenstiger sein")

        # Transport comparison
        transport_costs = self.compare_transport_modes(party, trip)
        cheapest = min(transport_costs, key=transport_costs.get)
        if transport_costs[cheapest] < breakdown.transport * 0.8:
            savings = breakdown.transport - transport_costs[cheapest]
            tips.append(f"Mit {cheapest.title()} ca. {savings:.0f} EUR sparen")

        return tips


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_budget_summary(resort: Dict, party: TravelParty,
                      trip: TripDetails, options: BudgetOptions,
                      transport_mode: TransportMode = TransportMode.CAR) -> Dict:
    """
    Create budget summary for a resort.
    """
    # Extract resort-specific prices
    resort_prices = {}
    if 'ticket_prices' in resort:
        tp = resort['ticket_prices']
        resort_prices['skipass_day_adult'] = tp.get('day_adult', 58)
        resort_prices['skipass_day_child'] = tp.get('day_child', 32)
        resort_prices['skipass_week_adult'] = tp.get('week_adult', 290)
        resort_prices['skipass_week_child'] = tp.get('week_child', 160)

    calc = BudgetCalculator(resort_prices)
    breakdown = calc.calculate_full_budget(party, trip, options, transport_mode)

    return {
        'total': round(breakdown.total, 2),
        'per_person': round(breakdown.per_person(party.total_persons), 2),
        'per_night': round(breakdown.total / trip.nights, 2),
        'breakdown': breakdown.to_dict(),
        'transport_comparison': calc.compare_transport_modes(party, trip),
        'savings_tips': calc.get_savings_tips(breakdown, party, trip)
    }


def format_currency(amount: float) -> str:
    """Format amount as currency string."""
    return f"{amount:,.0f} EUR".replace(",", ".")


def get_transport_mode_label(mode: TransportMode) -> str:
    """Get German label for transport mode."""
    labels = {
        TransportMode.CAR: "Auto",
        TransportMode.TRAIN: "Bahn",
        TransportMode.BUS: "Bus",
        TransportMode.FLIGHT: "Flug"
    }
    return labels.get(mode, mode.value)
