"""
Resort Comparison Module
Enables side-by-side comparison of up to 3 ski resorts.
"""

import pandas as pd
from typing import List, Dict, Optional


class ResortComparator:
    """
    Compares multiple resorts across various metrics.
    """

    # Metric definitions
    METRICS = {
        'slopes_km': {
            'label': 'Pistenkilometer',
            'unit': 'km',
            'higher_is_better': True,
            'category': 'size'
        },
        'lifts': {
            'label': 'Lifte',
            'unit': '',
            'higher_is_better': True,
            'category': 'size'
        },
        'altitude_m': {
            'label': 'Hoehe Tal',
            'unit': 'm',
            'higher_is_better': True,
            'category': 'quality'
        },
        'peak_altitude_m': {
            'label': 'Hoehe Berg',
            'unit': 'm',
            'higher_is_better': True,
            'category': 'quality'
        },
        'predicted_snow_cm': {
            'label': 'Schneevorhersage',
            'unit': 'cm',
            'higher_is_better': True,
            'category': 'quality'
        },
        'distance_km': {
            'label': 'Entfernung',
            'unit': 'km',
            'higher_is_better': False,
            'category': 'convenience'
        },
        'day_pass_price': {
            'label': 'Skipass/Tag',
            'unit': 'EUR',
            'higher_is_better': False,
            'category': 'price'
        },
        'snow_reliability': {
            'label': 'Schneesicherheit',
            'unit': '/5',
            'higher_is_better': True,
            'category': 'quality'
        },
        'apres_ski': {
            'label': 'Apres-Ski',
            'unit': '/5',
            'higher_is_better': True,
            'category': 'features'
        },
        'family_friendly': {
            'label': 'Familienfreundlich',
            'unit': '/5',
            'higher_is_better': True,
            'category': 'features'
        }
    }

    def __init__(self, resorts: List[Dict]):
        """
        Initialize comparator with resort data.

        Args:
            resorts: List of resort dictionaries (max 3)
        """
        if len(resorts) > 3:
            raise ValueError("Maximal 3 Resorts koennen verglichen werden")
        if len(resorts) < 2:
            raise ValueError("Mindestens 2 Resorts fuer Vergleich benoetigt")

        self.resorts = resorts
        self.resort_names = [r.get('name', f'Resort {i+1}') for i, r in enumerate(resorts)]

    def _get_metric_value(self, resort: Dict, metric_key: str) -> float:
        """Extract metric value from resort data."""
        if metric_key == 'day_pass_price':
            return resort.get('ticket_prices', {}).get('day_adult', 55)
        elif metric_key in ['snow_reliability', 'apres_ski', 'family_friendly']:
            return resort.get('ratings', {}).get(metric_key, 3)
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
