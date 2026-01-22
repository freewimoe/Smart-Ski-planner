"""
Resort Comparison Module
Enables side-by-side comparison of up to 3 ski resorts.
Enhanced with real snow conditions and accommodation pricing.
"""

import pandas as pd
from typing import List, Dict, Optional
from datetime import date, timedelta

# Import snow and accommodation modules
try:
    from snow_api import SnowConditionAggregator
    from snow_conditions import NormalizedSnowCondition
    SNOW_API_AVAILABLE = True
except ImportError:
    SNOW_API_AVAILABLE = False

try:
    from accommodation import AccommodationSearch, TravelGroup
    ACCOMMODATION_AVAILABLE = True
except ImportError:
    ACCOMMODATION_AVAILABLE = False


class ResortComparator:
    """
    Compares multiple resorts across various metrics.
    Enhanced with real-time snow data and accommodation prices.
    """

    # Metric definitions - Extended with snow and price metrics
    METRICS = {
        # Size metrics
        'slopes_km': {
            'label': 'Pistenkilometer',
            'unit': 'km',
            'higher_is_better': True,
            'category': 'size',
            'weight': 10
        },
        'lifts': {
            'label': 'Lifte',
            'unit': '',
            'higher_is_better': True,
            'category': 'size',
            'weight': 5
        },

        # Altitude metrics
        'altitude_m': {
            'label': 'Hoehe Tal',
            'unit': 'm',
            'higher_is_better': True,
            'category': 'altitude',
            'weight': 5
        },
        'peak_altitude_m': {
            'label': 'Hoehe Berg',
            'unit': 'm',
            'higher_is_better': True,
            'category': 'altitude',
            'weight': 8
        },

        # Real snow metrics (from API)
        'current_snow_base_cm': {
            'label': 'Schnee Tal',
            'unit': 'cm',
            'higher_is_better': True,
            'category': 'snow',
            'weight': 12
        },
        'current_snow_summit_cm': {
            'label': 'Schnee Berg',
            'unit': 'cm',
            'higher_is_better': True,
            'category': 'snow',
            'weight': 15
        },
        'fresh_snow_7days_cm': {
            'label': 'Neuschnee 7 Tage',
            'unit': 'cm',
            'higher_is_better': True,
            'category': 'snow',
            'weight': 12
        },
        'avalanche_risk': {
            'label': 'Lawinenrisiko',
            'unit': '/5',
            'higher_is_better': False,
            'category': 'safety',
            'weight': 10
        },

        # Legacy snow metric (ML prediction)
        'predicted_snow_cm': {
            'label': 'ML Vorhersage',
            'unit': 'cm',
            'higher_is_better': True,
            'category': 'snow',
            'weight': 5
        },

        # Price metrics
        'day_pass_price': {
            'label': 'Skipass/Tag',
            'unit': 'EUR',
            'higher_is_better': False,
            'category': 'price',
            'weight': 8
        },
        'week_pass_price': {
            'label': 'Skipass/Woche',
            'unit': 'EUR',
            'higher_is_better': False,
            'category': 'price',
            'weight': 8
        },
        'accommodation_price': {
            'label': 'Unterkunft/Nacht',
            'unit': 'EUR',
            'higher_is_better': False,
            'category': 'price',
            'weight': 10
        },

        # Convenience metrics
        'distance_km': {
            'label': 'Anfahrt',
            'unit': 'km',
            'higher_is_better': False,
            'category': 'convenience',
            'weight': 8
        },
        'slope_availability': {
            'label': 'Pisten offen',
            'unit': '%',
            'higher_is_better': True,
            'category': 'convenience',
            'weight': 8
        },

        # Rating metrics
        'snow_reliability': {
            'label': 'Schneesicherheit',
            'unit': '/5',
            'higher_is_better': True,
            'category': 'quality',
            'weight': 6
        },
        'apres_ski': {
            'label': 'Apres-Ski',
            'unit': '/5',
            'higher_is_better': True,
            'category': 'features',
            'weight': 4
        },
        'family_friendly': {
            'label': 'Familienfreundlich',
            'unit': '/5',
            'higher_is_better': True,
            'category': 'features',
            'weight': 4
        },

        # Overall scores
        'overall_snow_score': {
            'label': 'Schnee-Score',
            'unit': '/100',
            'higher_is_better': True,
            'category': 'score',
            'weight': 15
        }
    }

    # Category weights for overall comparison
    CATEGORY_WEIGHTS = {
        'snow': 30,           # Real snow conditions
        'price': 25,          # Ski pass + accommodation
        'convenience': 15,    # Distance, availability
        'safety': 10,         # Avalanche risk
        'size': 10,           # Slopes, lifts
        'quality': 5,         # Ratings
        'features': 5         # Apres-ski, family
    }

    def __init__(self, resorts: List[Dict], fetch_live_data: bool = True):
        """
        Initialize comparator with resort data.

        Args:
            resorts: List of resort dictionaries (max 3)
            fetch_live_data: Whether to fetch live snow/price data
        """
        if len(resorts) > 3:
            raise ValueError("Maximal 3 Resorts koennen verglichen werden")
        if len(resorts) < 2:
            raise ValueError("Mindestens 2 Resorts fuer Vergleich benoetigt")

        self.resorts = resorts
        self.resort_names = [r.get('name', f'Resort {i+1}') for i, r in enumerate(resorts)]
        self.snow_conditions = {}
        self.accommodation_prices = {}

        if fetch_live_data:
            self._fetch_live_data()

    def _fetch_live_data(self):
        """Fetch live snow and accommodation data for all resorts."""
        # Fetch snow conditions
        if SNOW_API_AVAILABLE:
            try:
                aggregator = SnowConditionAggregator()
                for resort in self.resorts:
                    name = resort.get('name', '')
                    condition = aggregator.get_conditions(resort)
                    self.snow_conditions[name] = condition
            except Exception as e:
                print(f"Snow data fetch error: {e}")

        # Fetch accommodation prices
        if ACCOMMODATION_AVAILABLE:
            try:
                search = AccommodationSearch()
                checkin = date.today() + timedelta(days=30)
                checkout = checkin + timedelta(days=7)
                group = TravelGroup(adults=2, children=0, rooms=1)

                for resort in self.resorts:
                    name = resort.get('name', '')
                    result = search.search(resort, checkin, checkout, group)
                    self.accommodation_prices[name] = result.price_range.get('average', 0) / 7
            except Exception as e:
                print(f"Accommodation data fetch error: {e}")

    def _get_metric_value(self, resort: Dict, metric_key: str) -> float:
        """Extract metric value from resort data, including live data."""
        name = resort.get('name', '')

        # Live snow data
        if metric_key in ['current_snow_base_cm', 'current_snow_summit_cm',
                          'fresh_snow_7days_cm', 'avalanche_risk',
                          'overall_snow_score', 'slope_availability']:
            condition = self.snow_conditions.get(name)
            if condition:
                if metric_key == 'current_snow_base_cm':
                    return condition.snow_depth.base_depth_cm
                elif metric_key == 'current_snow_summit_cm':
                    return condition.snow_depth.summit_depth_cm
                elif metric_key == 'fresh_snow_7days_cm':
                    return condition.fresh_snow.last_7days_cm
                elif metric_key == 'avalanche_risk':
                    return condition.avalanche.risk_level.value
                elif metric_key == 'overall_snow_score':
                    return condition.overall_score
                elif metric_key == 'slope_availability':
                    return condition.piste.slope_availability
            return 0

        # Live accommodation price
        if metric_key == 'accommodation_price':
            return self.accommodation_prices.get(name, 0)

        # Ticket prices
        if metric_key == 'day_pass_price':
            return resort.get('ticket_prices', {}).get('day_adult', 55)
        elif metric_key == 'week_pass_price':
            return resort.get('ticket_prices', {}).get('week_adult', 290)

        # Ratings
        elif metric_key in ['snow_reliability', 'apres_ski', 'family_friendly']:
            return resort.get('ratings', {}).get(metric_key, 3)

        # Default
        else:
            return resort.get(metric_key, 0)

    def _normalize_value(self, value: float, min_val: float,
                        max_val: float, higher_is_better: bool) -> float:
        """Normalize value to 0-100 scale."""
        if max_val == min_val:
            return 50

        normalized = (value - min_val) / (max_val - min_val) * 100

        if not higher_is_better:
            normalized = 100 - normalized

        return normalized

    def get_comparison_table(self) -> pd.DataFrame:
        """Create comparison table."""
        rows = []

        for metric_key, metric_info in self.METRICS.items():
            values = []
            for resort in self.resorts:
                val = self._get_metric_value(resort, metric_key)
                values.append(val)

            # Skip if all values are 0 or missing
            if all(v == 0 for v in values):
                continue

            row = {
                'Metrik': metric_info['label'],
                'Einheit': metric_info['unit']
            }

            for i, (name, val) in enumerate(zip(self.resort_names, values)):
                if metric_info['unit'] == '/5':
                    row[name] = f"{val:.1f}"
                elif metric_info['unit'] in ['km', 'm', 'cm']:
                    row[name] = f"{val:.0f}"
                elif metric_info['unit'] == 'EUR':
                    row[name] = f"{val:.0f}"
                else:
                    row[name] = f"{val}"

            # Mark best resort
            if metric_info['higher_is_better']:
                best_idx = values.index(max(values))
            else:
                best_idx = values.index(min(values))
            row['Bester'] = self.resort_names[best_idx]

            rows.append(row)

        return pd.DataFrame(rows)

    def get_radar_data(self) -> Dict:
        """
        Get data formatted for radar chart visualization.

        Returns:
            Dict with categories and normalized values per resort
        """
        categories = []
        resort_data = {name: [] for name in self.resort_names}

        for metric_key, metric_info in self.METRICS.items():
            # Collect all values for this metric
            all_values = []
            for resort in self.resorts:
                val = self._get_metric_value(resort, metric_key)
                all_values.append(val)

            # Skip if all zeros
            if all(v == 0 for v in all_values):
                continue

            categories.append(metric_info['label'])
            min_val = min(all_values)
            max_val = max(all_values)

            # Normalize values for each resort
            for i, (name, val) in enumerate(zip(self.resort_names, all_values)):
                normalized = self._normalize_value(
                    val, min_val, max_val,
                    metric_info['higher_is_better']
                )
                resort_data[name].append(round(normalized, 1))

        return {
            'categories': categories,
            'resorts': resort_data
        }

    def calculate_winner(self) -> Dict:
        """
        Calculate overall winner based on all metrics.

        Returns:
            Dict with winner name, scores, and margin
        """
        scores = {name: 0 for name in self.resort_names}
        metric_count = 0

        for metric_key, metric_info in self.METRICS.items():
            values = []
            for resort in self.resorts:
                val = self._get_metric_value(resort, metric_key)
                values.append(val)

            # Skip if all zeros
            if all(v == 0 for v in values):
                continue

            metric_count += 1
            min_val = min(values)
            max_val = max(values)

            for i, (name, val) in enumerate(zip(self.resort_names, values)):
                normalized = self._normalize_value(
                    val, min_val, max_val,
                    metric_info['higher_is_better']
                )
                scores[name] += normalized

        # Average scores
        if metric_count > 0:
            scores = {name: score / metric_count for name, score in scores.items()}

        winner = max(scores, key=scores.get)
        sorted_scores = sorted(scores.values(), reverse=True)
        margin = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else 0

        return {
            'winner': winner,
            'scores': {name: round(score, 1) for name, score in scores.items()},
            'margin': round(margin, 1)
        }

    def get_pros_cons(self, resort_name: str) -> Dict[str, List[str]]:
        """
        Determine strengths and weaknesses of a resort compared to others.
        """
        resort_idx = self.resort_names.index(resort_name)
        resort = self.resorts[resort_idx]

        pros = []
        cons = []

        for metric_key, metric_info in self.METRICS.items():
            val = self._get_metric_value(resort, metric_key)

            # Compare with others
            other_values = []
            for i, r in enumerate(self.resorts):
                if i != resort_idx:
                    other_values.append(self._get_metric_value(r, metric_key))

            if not other_values:
                continue

            avg_other = sum(other_values) / len(other_values)
            label = metric_info['label']

            if avg_other == 0:
                continue

            if metric_info['higher_is_better']:
                if val > avg_other * 1.15:  # 15% better
                    pros.append(f"Beste(r) {label}")
                elif val < avg_other * 0.85:  # 15% worse
                    cons.append(f"Niedrigste(r) {label}")
            else:
                if val < avg_other * 0.85:  # 15% lower (better for price/distance)
                    pros.append(f"Guenstigste(r) {label}")
                elif val > avg_other * 1.15:
                    cons.append(f"Hoechste(r) {label}")

        return {'pros': pros[:3], 'cons': cons[:3]}

    def get_category_comparison(self) -> Dict[str, Dict]:
        """
        Get comparison grouped by category.
        """
        categories = {}

        for metric_key, metric_info in self.METRICS.items():
            cat = metric_info['category']
            if cat not in categories:
                categories[cat] = {'metrics': [], 'winner': None, 'total_score': {}}

            values = []
            for resort in self.resorts:
                val = self._get_metric_value(resort, metric_key)
                values.append(val)

            if all(v == 0 for v in values):
                continue

            categories[cat]['metrics'].append({
                'key': metric_key,
                'label': metric_info['label'],
                'values': dict(zip(self.resort_names, values)),
                'higher_is_better': metric_info['higher_is_better']
            })

            # Track scores per category
            min_val = min(values)
            max_val = max(values)
            for name, val in zip(self.resort_names, values):
                if name not in categories[cat]['total_score']:
                    categories[cat]['total_score'][name] = 0
                normalized = self._normalize_value(val, min_val, max_val,
                                                   metric_info['higher_is_better'])
                categories[cat]['total_score'][name] += normalized

        # Determine category winners
        for cat_data in categories.values():
            if cat_data['total_score']:
                cat_data['winner'] = max(cat_data['total_score'],
                                         key=cat_data['total_score'].get)

        return categories


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def create_comparison_summary(resorts: List[Dict]) -> str:
    """
    Create a text summary of the comparison.
    """
    comparator = ResortComparator(resorts)
    result = comparator.calculate_winner()

    summary = f"Vergleich von {len(resorts)} Skigebieten:\n\n"

    for name in comparator.resort_names:
        score = result['scores'].get(name, 0)
        pros_cons = comparator.get_pros_cons(name)

        summary += f"{name} ({score:.0f} Punkte):\n"
        for pro in pros_cons['pros']:
            summary += f"  + {pro}\n"
        for con in pros_cons['cons']:
            summary += f"  - {con}\n"
        summary += "\n"

    summary += f"Gesamtsieger: {result['winner']} "
    summary += f"(Vorsprung: +{result['margin']:.0f} Punkte)"

    return summary


def get_metric_icon(category: str) -> str:
    """Get icon for metric category."""
    icons = {
        'size': '📏',
        'quality': '⭐',
        'convenience': '🚗',
        'price': '💰',
        'features': '🎯'
    }
    return icons.get(category, '📊')


def format_comparison_for_display(comparator: ResortComparator) -> Dict:
    """
    Format comparison data for UI display.
    """
    return {
        'table': comparator.get_comparison_table(),
        'radar_data': comparator.get_radar_data(),
        'winner': comparator.calculate_winner(),
        'pros_cons': {
            name: comparator.get_pros_cons(name)
            for name in comparator.resort_names
        },
        'categories': comparator.get_category_comparison()
    }


# =============================================================================
# ENHANCED COMPARISON FUNCTIONS
# =============================================================================

def create_snow_comparison_table(resorts: List[Dict]) -> pd.DataFrame:
    """
    Create a detailed snow conditions comparison table.
    """
    if not SNOW_API_AVAILABLE:
        return pd.DataFrame({'Fehler': ['Snow API nicht verfuegbar']})

    aggregator = SnowConditionAggregator()
    rows = []

    for resort in resorts:
        condition = aggregator.get_conditions(resort)

        rows.append({
            'Resort': resort.get('name', ''),
            'Schnee Tal (cm)': round(condition.snow_depth.base_depth_cm, 0),
            'Schnee Mitte (cm)': round(condition.snow_depth.mid_depth_cm, 0),
            'Schnee Berg (cm)': round(condition.snow_depth.summit_depth_cm, 0),
            'Neuschnee 24h': round(condition.fresh_snow.last_24h_cm, 0),
            'Neuschnee 7d': round(condition.fresh_snow.last_7days_cm, 0),
            'Lawinenrisiko': condition.avalanche.risk_level.value,
            'Temperatur': f"{condition.current_temp_c:.1f}°C",
            'Bewertung': f"{condition.overall_score:.0f}/100",
            'Qualitaet': condition.snow_quality_rating
        })

    return pd.DataFrame(rows)


def create_price_comparison_table(
    resorts: List[Dict],
    adults: int = 2,
    children: int = 0,
    nights: int = 7
) -> pd.DataFrame:
    """
    Create a detailed price comparison table.
    """
    if not ACCOMMODATION_AVAILABLE:
        # Fallback to basic comparison
        rows = []
        for resort in resorts:
            tp = resort.get('ticket_prices', {})
            rows.append({
                'Resort': resort.get('name', ''),
                'Tagespass': f"{tp.get('day_adult', 55)} EUR",
                'Wochenpass': f"{tp.get('week_adult', 290)} EUR"
            })
        return pd.DataFrame(rows)

    from accommodation import AccommodationSearch, TravelGroup

    search = AccommodationSearch()
    checkin = date.today() + timedelta(days=30)
    checkout = checkin + timedelta(days=nights)
    group = TravelGroup(adults=adults, children=children, rooms=1)

    rows = []
    for resort in resorts:
        result = search.search(resort, checkin, checkout, group)
        tp = resort.get('ticket_prices', {})

        # Calculate total trip cost
        ski_pass_cost = tp.get('week_adult', 290) * adults
        if children > 0:
            ski_pass_cost += tp.get('week_child', 160) * children

        accommodation_cost = result.price_range.get('average', 0)
        total_cost = ski_pass_cost + accommodation_cost

        rows.append({
            'Resort': resort.get('name', ''),
            'Tagespass': f"{tp.get('day_adult', 55)} EUR",
            'Wochenpass': f"{tp.get('week_adult', 290)} EUR",
            'Unterkunft (ges.)': f"{accommodation_cost:.0f} EUR",
            'Unterkunft/Nacht': f"{accommodation_cost/nights:.0f} EUR",
            'Gesamtkosten': f"{total_cost:.0f} EUR",
            'Booking URL': result.search_url[:50] + '...'
        })

    df = pd.DataFrame(rows)
    return df.sort_values('Gesamtkosten', key=lambda x: x.str.extract(r'(\d+)')[0].astype(float))


def create_comprehensive_comparison(resorts: List[Dict]) -> Dict:
    """
    Create comprehensive comparison with all available data.
    """
    comparator = ResortComparator(resorts, fetch_live_data=True)

    result = {
        'basic': format_comparison_for_display(comparator),
        'snow': {},
        'prices': {},
        'recommendations': []
    }

    # Snow comparison
    if SNOW_API_AVAILABLE:
        result['snow'] = {
            'table': create_snow_comparison_table(resorts).to_dict('records'),
            'best_snow': None,
            'best_fresh_snow': None,
            'safest': None
        }

        # Find bests
        if comparator.snow_conditions:
            conditions = list(comparator.snow_conditions.values())
            result['snow']['best_snow'] = max(
                conditions, key=lambda c: c.snow_depth.average_depth_cm
            ).resort_name
            result['snow']['best_fresh_snow'] = max(
                conditions, key=lambda c: c.fresh_snow.last_7days_cm
            ).resort_name
            result['snow']['safest'] = min(
                conditions,
                key=lambda c: c.avalanche.risk_level.value if c.avalanche.risk_level.value > 0 else 10
            ).resort_name

    # Price comparison
    if ACCOMMODATION_AVAILABLE:
        result['prices'] = {
            'table': create_price_comparison_table(resorts).to_dict('records'),
            'cheapest': None
        }

        if comparator.accommodation_prices:
            result['prices']['cheapest'] = min(
                comparator.accommodation_prices.items(),
                key=lambda x: x[1]
            )[0]

    # Generate recommendations
    winner = result['basic']['winner']
    result['recommendations'] = [
        f"Gesamtsieger: {winner['winner']} mit {winner['scores'].get(winner['winner'], 0):.0f} Punkten"
    ]

    if result['snow'].get('best_snow'):
        result['recommendations'].append(
            f"Beste Schneebedingungen: {result['snow']['best_snow']}"
        )

    if result['prices'].get('cheapest'):
        result['recommendations'].append(
            f"Guenstigstes Resort: {result['prices']['cheapest']}"
        )

    return result


def get_resort_comparison_summary(resorts: List[Dict]) -> str:
    """
    Generate a text summary of resort comparison.
    """
    comparison = create_comprehensive_comparison(resorts)

    summary_lines = [
        "=== Skiresort-Vergleich ===",
        ""
    ]

    # Basic winner
    winner = comparison['basic']['winner']
    summary_lines.append(f"Gesamtsieger: {winner['winner']}")
    summary_lines.append(f"  Vorsprung: +{winner['margin']:.0f} Punkte")
    summary_lines.append("")

    # Snow conditions
    if comparison['snow']:
        summary_lines.append("Schneebedingungen:")
        summary_lines.append(f"  Meiste Schnee: {comparison['snow'].get('best_snow', 'N/A')}")
        summary_lines.append(f"  Meiste Neuschnee: {comparison['snow'].get('best_fresh_snow', 'N/A')}")
        summary_lines.append(f"  Sicherster: {comparison['snow'].get('safest', 'N/A')}")
        summary_lines.append("")

    # Prices
    if comparison['prices']:
        summary_lines.append("Preise:")
        summary_lines.append(f"  Guenstigster: {comparison['prices'].get('cheapest', 'N/A')}")
        summary_lines.append("")

    # Pros/Cons for each
    summary_lines.append("Details pro Resort:")
    for name in [r.get('name', '') for r in resorts]:
        pros_cons = comparison['basic']['pros_cons'].get(name, {})
        summary_lines.append(f"\n{name}:")
        for pro in pros_cons.get('pros', []):
            summary_lines.append(f"  + {pro}")
        for con in pros_cons.get('cons', []):
            summary_lines.append(f"  - {con}")

    return "\n".join(summary_lines)
