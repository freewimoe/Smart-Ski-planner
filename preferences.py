"""
User Preferences and Resort Matching Algorithm
Calculates personalized scores for resorts based on user preferences.
"""

import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class UserPreferences:
    """User preferences for resort matching."""
    skill_level: str = 'intermediate'      # beginner, intermediate, expert
    budget_level: str = 'medium'           # low, medium, high
    max_distance_km: int = 500
    prefer_apres_ski: bool = False
    prefer_family: bool = False
    prefer_snow_guarantee: bool = True
    prefer_terrain_park: bool = False
    prefer_cross_country: bool = False
    min_slopes_km: int = 50

    @classmethod
    def from_dict(cls, data: Dict) -> 'UserPreferences':
        """Create UserPreferences from dictionary."""
        return cls(
            skill_level=data.get('skill_level', 'intermediate'),
            budget_level=data.get('budget_level', 'medium'),
            max_distance_km=data.get('max_distance_km', 500),
            prefer_apres_ski=bool(data.get('prefer_apres_ski', False)),
            prefer_family=bool(data.get('prefer_family', False)),
            prefer_snow_guarantee=bool(data.get('prefer_snow_guarantee', True)),
            prefer_terrain_park=bool(data.get('prefer_terrain_park', False)),
            prefer_cross_country=bool(data.get('prefer_cross_country', False)),
            min_slopes_km=data.get('min_slopes_km', 50)
        )


class ResortMatcher:
    """
    Calculates personalized scores for resorts based on user preferences.
    """

    # Weight distribution for different factors (must sum to 100)
    WEIGHTS = {
        'difficulty_match': 25,
        'budget_match': 20,
        'snow_score': 20,
        'distance_score': 15,
        'features_match': 10,
        'size_score': 10
    }

    # Budget ranges based on day pass prices
    BUDGET_RANGES = {
        'low': (0, 45),       # Skipass < 45 EUR/day
        'medium': (45, 70),   # Skipass 45-70 EUR/day
        'high': (70, 200)     # Skipass > 70 EUR/day
    }

    def __init__(self, user_prefs: UserPreferences):
        self.prefs = user_prefs

    def calculate_difficulty_score(self, resort: Dict) -> float:
        """
        Calculate how well the slope distribution matches the user's skill level.
        Returns score 0-100.
        """
        difficulty = resort.get('difficulty', {})
        if not difficulty:
            return 50  # Default score if no data

        # Ideal distribution per skill level
        ideal = {
            'beginner': {'beginner': 50, 'intermediate': 40, 'expert': 10},
            'intermediate': {'beginner': 25, 'intermediate': 50, 'expert': 25},
            'expert': {'beginner': 10, 'intermediate': 30, 'expert': 60}
        }

        user_ideal = ideal.get(self.prefs.skill_level, ideal['intermediate'])

        # Calculate deviation (0 = perfect match, higher = worse)
        deviation = sum(
            abs(difficulty.get(level, 33) - user_ideal[level])
            for level in ['beginner', 'intermediate', 'expert']
        ) / 3

        return max(0, 100 - deviation)

    def calculate_budget_score(self, resort: Dict) -> float:
        """
        Calculate how well the price matches the user's budget level.
        Returns score 0-100.
        """
        ticket_prices = resort.get('ticket_prices', {})
        day_price = ticket_prices.get('day_adult', 55)

        low, high = self.BUDGET_RANGES.get(self.prefs.budget_level, (45, 70))

        if low <= day_price <= high:
            return 100
        elif day_price < low:
            # Cheaper than desired = okay but not ideal
            return 85
        else:
            # More expensive than budget
            over_budget = day_price - high
            return max(0, 100 - (over_budget * 2.5))  # -2.5 points per EUR over budget

    def calculate_distance_score(self, distance_km: float) -> float:
        """
        Calculate score based on distance (closer = better, within limits).
        Returns score 0-100.
        """
        if distance_km > self.prefs.max_distance_km:
            return 0

        # Linear: 100 at 0km, 50 at max_distance
        return 100 - (distance_km / self.prefs.max_distance_km * 50)

    def calculate_snow_score(self, predicted_snow_cm: float, resort: Dict) -> float:
        """
        Calculate score based on predicted snow and snow reliability.
        Returns score 0-100.
        """
        # Base score from predicted snow (100cm = max)
        base_score = min(100, predicted_snow_cm)

        # Bonus for glacier (guaranteed snow)
        features = resort.get('features', {})
        if features.get('glacier', False):
            base_score = min(100, base_score + 15)

        # Bonus for snow cannons coverage
        snow_cannons_km = features.get('snow_cannons_km', 0)
        slopes_km = resort.get('slopes_km', 50)
        cannon_coverage = (snow_cannons_km / slopes_km * 100) if slopes_km > 0 else 0
        base_score = min(100, base_score + cannon_coverage * 0.1)

        return base_score

    def calculate_features_score(self, resort: Dict) -> float:
        """
        Calculate bonus score for desired features.
        Returns score 0-100.
        """
        score = 50  # Base score
        features = resort.get('features', {})
        ratings = resort.get('ratings', {})

        # Apres-Ski preference
        if self.prefs.prefer_apres_ski:
            apres_rating = ratings.get('apres_ski', 3)
            score += apres_rating * 5  # max +25

        # Family-friendly preference
        if self.prefs.prefer_family:
            family_rating = ratings.get('family_friendly', 3)
            score += family_rating * 5  # max +25

        # Snow guarantee preference
        if self.prefs.prefer_snow_guarantee:
            snow_rating = ratings.get('snow_reliability', 3)
            if features.get('glacier', False):
                snow_rating += 2
            score += snow_rating * 4  # max +20

        # Terrain park preference
        if self.prefs.prefer_terrain_park:
            if features.get('terrain_park', False):
                score += 15

        # Cross-country preference
        if self.prefs.prefer_cross_country:
            xc_km = features.get('cross_country_km', 0)
            score += min(20, xc_km / 2)  # max +20 at 40km

        return min(100, score)

    def calculate_size_score(self, resort: Dict) -> float:
        """
        Calculate score based on resort size (slopes km).
        Returns score 0-100.
        """
        slopes_km = resort.get('slopes_km', 0)

        if slopes_km < self.prefs.min_slopes_km:
            # Below minimum: penalty
            return max(0, 50 * (slopes_km / self.prefs.min_slopes_km))

        # Bonus for larger resorts (up to 300km)
        return min(100, 70 + (slopes_km / 10))

    def calculate_total_score(self, resort: Dict, distance_km: float,
                              predicted_snow_cm: float) -> Dict:
        """
        Calculate weighted total score with breakdown.

        Returns:
            Dict with total_score and breakdown for transparency
        """
        scores = {
            'difficulty_match': self.calculate_difficulty_score(resort),
            'budget_match': self.calculate_budget_score(resort),
            'snow_score': self.calculate_snow_score(predicted_snow_cm, resort),
            'distance_score': self.calculate_distance_score(distance_km),
            'features_match': self.calculate_features_score(resort),
            'size_score': self.calculate_size_score(resort)
        }

        # Calculate weighted total
        total = sum(
            scores[key] * (self.WEIGHTS[key] / 100)
            for key in scores
        )

        # Find strengths and weaknesses
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        return {
            'total_score': round(total, 1),
            'breakdown': scores,
            'top_strength': sorted_scores[0][0],
            'top_weakness': sorted_scores[-1][0]
        }

    def rank_resorts(self, resorts_df: pd.DataFrame,
                     resort_details: Dict[str, Dict]) -> pd.DataFrame:
        """
        Rank all resorts by personalized match scores.

        Args:
            resorts_df: DataFrame with basic resort data and predictions
            resort_details: Dict mapping resort names to full details from JSON

        Returns:
            DataFrame with match scores and rankings
        """
        results = []

        for _, row in resorts_df.iterrows():
            resort_name = row['name']
            details = resort_details.get(resort_name, row.to_dict())

            score_data = self.calculate_total_score(
                details,
                row.get('distance_km', 0),
                row.get('predicted_snow_cm', 0)
            )

            results.append({
                'name': resort_name,
                'match_score': score_data['total_score'],
                'top_strength': self._format_score_label(score_data['top_strength']),
                'top_weakness': self._format_score_label(score_data['top_weakness']),
                **{k: round(v, 1) for k, v in score_data['breakdown'].items()}
            })

        result_df = pd.DataFrame(results)
        return result_df.sort_values('match_score', ascending=False)

    def _format_score_label(self, key: str) -> str:
        """Convert score key to human-readable label."""
        labels = {
            'difficulty_match': 'Schwierigkeit',
            'budget_match': 'Preis',
            'snow_score': 'Schnee',
            'distance_score': 'Entfernung',
            'features_match': 'Features',
            'size_score': 'Groesse'
        }
        return labels.get(key, key)

    def get_recommendation_text(self, resort: Dict, score_data: Dict) -> str:
        """
        Generate a recommendation text explaining why this resort matches.
        """
        total = score_data['total_score']
        strength = self._format_score_label(score_data['top_strength'])
        weakness = self._format_score_label(score_data['top_weakness'])

        if total >= 80:
            match_text = "Hervorragende Wahl"
        elif total >= 65:
            match_text = "Gute Wahl"
        elif total >= 50:
            match_text = "Akzeptable Wahl"
        else:
            match_text = "Weniger geeignet"

        return (
            f"{match_text} ({total:.0f}% Match). "
            f"Staerke: {strength}. "
            f"Beachte: {weakness}."
        )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_skill_level_description(level: str) -> str:
    """Return description for skill level."""
    descriptions = {
        'beginner': 'Anfaenger - Bevorzugt blaue Pisten und breite Abfahrten',
        'intermediate': 'Fortgeschritten - Mix aus blauen und roten Pisten',
        'expert': 'Experte - Bevorzugt rote und schwarze Pisten, Freeride'
    }
    return descriptions.get(level, descriptions['intermediate'])


def get_budget_level_description(level: str) -> str:
    """Return description for budget level."""
    descriptions = {
        'low': 'Sparsam - Skipass unter 45 EUR/Tag',
        'medium': 'Mittel - Skipass 45-70 EUR/Tag',
        'high': 'Komfort - Skipass ueber 70 EUR/Tag'
    }
    return descriptions.get(level, descriptions['medium'])


def calculate_difficulty_match_simple(user_skill: str, resort_difficulty: Dict) -> int:
    """
    Simple difficulty match calculation.
    Returns percentage match (0-100).
    """
    if not resort_difficulty:
        return 50

    skill_weights = {
        'beginner': {'beginner': 1.0, 'intermediate': 0.3, 'expert': 0.0},
        'intermediate': {'beginner': 0.4, 'intermediate': 1.0, 'expert': 0.5},
        'expert': {'beginner': 0.1, 'intermediate': 0.5, 'expert': 1.0}
    }

    weights = skill_weights.get(user_skill, skill_weights['intermediate'])
    score = sum(
        resort_difficulty.get(level, 33) * weights[level]
        for level in ['beginner', 'intermediate', 'expert']
    )
    return min(100, int(score))
