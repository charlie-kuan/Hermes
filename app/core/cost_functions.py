"""Cost functions for route optimization."""

from typing import Dict

from app.models.domain import Edge, TrailDifficulty


class RoutingCostFunction:
    """Calculates routing costs based on distance, elevation, and difficulty."""

    # Default preference weights
    DEFAULT_WEIGHTS = {
        'distance': 1.0,
        'elevation': 0.5,
        'difficulty': 0.3,
        'popularity': 0.0  # 0 = ignore popularity, higher = prefer popular trails
    }

    # Difficulty cost multipliers
    DIFFICULTY_COSTS = {
        TrailDifficulty.EASY: 1.0,
        TrailDifficulty.MODERATE: 1.3,
        TrailDifficulty.DIFFICULT: 1.7,
        TrailDifficulty.EXPERT: 2.5,
    }

    def __init__(self, preferences: Dict[str, float] = None):
        """
        Initialize cost function with preference weights.

        Args:
            preferences: Dictionary of preference weights
                - distance: Weight for distance component
                - elevation: Weight for elevation component
                - difficulty: Weight for difficulty component
        """
        self.preferences = preferences or self.DEFAULT_WEIGHTS

    def calculate_edge_cost(self, edge: Edge) -> float:
        """
        Calculate cost for traversing an edge.

        Cost = w_dist * normalized_distance
             + w_elev * elevation_factor
             + w_diff * difficulty_multiplier
             - w_pop * popularity_bonus  (lower cost for popular trails)

        Args:
            edge: Edge to calculate cost for

        Returns:
            Cost value (lower is better)
        """
        # Distance component (normalize to km)
        base_distance = edge.distance / 1000.0

        # Elevation component (per 100m of gain)
        elevation_factor = edge.elevation_gain / 100.0

        # Difficulty component
        difficulty_multiplier = self.DIFFICULTY_COSTS[edge.difficulty]

        # Popularity component (invert: higher popularity = lower cost)
        # Score range: 0.5-2.0, normalize to 0-1, then subtract from cost
        popularity_bonus = (edge.popularity_score - 0.5) / 1.5  # Range 0-1

        # Weighted sum
        cost = (
            self.preferences['distance'] * base_distance +
            self.preferences['elevation'] * elevation_factor +
            self.preferences['difficulty'] * (difficulty_multiplier - 1.0) -  # Normalized so EASY = 0
            self.preferences['popularity'] * popularity_bonus  # Negative = reduction in cost
        )

        return max(0.1, cost)  # Minimum cost to avoid zero-weight edges

    def calculate_heuristic(
        self,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float
    ) -> float:
        """
        Calculate heuristic cost for A* algorithm (straight-line distance).

        Args:
            from_lat, from_lon: Source coordinates
            to_lat, to_lon: Target coordinates

        Returns:
            Heuristic cost estimate
        """
        from app.utils.geo_utils import haversine_distance

        distance_m = haversine_distance(from_lat, from_lon, to_lat, to_lon)
        distance_km = distance_m / 1000.0

        # Apply distance weight
        return self.preferences['distance'] * distance_km

    def adjust_for_scenic_route(self, edge: Edge, scenic_boost: float = 0.8) -> float:
        """
        Adjust cost to prefer scenic routes (peaks, viewpoints).

        Args:
            edge: Edge to calculate cost for
            scenic_boost: Multiplier for scenic routes (< 1.0 reduces cost)

        Returns:
            Adjusted cost
        """
        base_cost = self.calculate_edge_cost(edge)

        # Check if edge leads to scenic point
        # (This would need to check node types in actual implementation)
        # For now, prefer trails with names as they're likely more scenic
        if edge.trail_name:
            return base_cost * scenic_boost

        return base_cost

    def adjust_for_avoid_difficult(self, edge: Edge, avoid_penalty: float = 2.0) -> float:
        """
        Adjust cost to avoid difficult terrain.

        Args:
            edge: Edge to calculate cost for
            avoid_penalty: Multiplier for difficult trails

        Returns:
            Adjusted cost
        """
        base_cost = self.calculate_edge_cost(edge)

        if edge.difficulty in [TrailDifficulty.DIFFICULT, TrailDifficulty.EXPERT]:
            return base_cost * avoid_penalty

        return base_cost

    def set_preference(self, preference: str, weight: float) -> None:
        """
        Update a preference weight.

        Args:
            preference: Preference name (distance, elevation, difficulty)
            weight: New weight value
        """
        if preference in self.preferences:
            self.preferences[preference] = max(0.0, weight)

    def optimize_for_speed(self) -> None:
        """Optimize preferences for fastest route."""
        self.preferences = {
            'distance': 1.0,
            'elevation': 0.3,
            'difficulty': 0.2
        }

    def optimize_for_scenic(self) -> None:
        """Optimize preferences for scenic route."""
        self.preferences = {
            'distance': 0.7,
            'elevation': 1.0,  # Prefer elevation gain (peaks, ridges)
            'difficulty': 0.1
        }

    def optimize_for_easy(self) -> None:
        """Optimize preferences for easiest route."""
        self.preferences = {
            'distance': 0.8,
            'elevation': 0.5,
            'difficulty': 1.5,  # Heavily penalize difficult terrain
            'popularity': 0.0
        }

    def optimize_for_popular(self) -> None:
        """Optimize preferences for popular, well-traveled routes."""
        self.preferences = {
            'distance': 0.8,
            'elevation': 0.4,
            'difficulty': 0.8,
            'popularity': 1.5  # Strongly prefer popular trails
        }
