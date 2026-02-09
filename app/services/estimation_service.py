"""Time and effort estimation service."""

from typing import Tuple

from loguru import logger

from app.core.time_estimators import TimeEstimator
from app.models.domain import FitnessLevel, Route, RouteSegment, TrailDifficulty


class EstimationService:
    """Handles time and effort estimation for routes."""

    def __init__(self):
        self.time_estimator = TimeEstimator()

    def estimate_route(
        self,
        route: Route,
        fitness_level: str = "moderate",
        pack_weight_kg: float = 12.0
    ) -> Tuple[float, float, float]:
        """
        Estimate time for a complete route.

        Args:
            route: Route to estimate
            fitness_level: Hiker fitness level
            pack_weight_kg: Pack weight

        Returns:
            Tuple of (optimistic, normal, conservative) times in hours
        """
        fitness = FitnessLevel(fitness_level)

        # Estimate total time
        optimistic, normal, conservative = self.time_estimator.estimate_with_scenarios(
            route.total_distance,
            route.total_elevation_gain,
            route.total_elevation_loss,
            route.difficulty,
            fitness,
            pack_weight_kg
        )

        logger.info(
            f"Route estimated: {normal:.1f}h "
            f"(optimistic: {optimistic:.1f}h, conservative: {conservative:.1f}h)"
        )

        return optimistic, normal, conservative

    def estimate_segment(
        self,
        segment: RouteSegment,
        fitness_level: str = "moderate",
        pack_weight_kg: float = 12.0
    ) -> float:
        """
        Estimate time for a single route segment.

        Args:
            segment: Route segment
            fitness_level: Hiker fitness level
            pack_weight_kg: Pack weight

        Returns:
            Estimated time in hours
        """
        fitness = FitnessLevel(fitness_level)

        time = self.time_estimator.estimate_segment_time(
            segment.distance,
            segment.elevation_gain,
            segment.elevation_loss,
            segment.difficulty,
            fitness,
            pack_weight_kg
        )

        return time

    def estimate_all_segments(
        self,
        route: Route,
        fitness_level: str = "moderate",
        pack_weight_kg: float = 12.0
    ) -> Route:
        """
        Update route with estimated times for all segments.

        Args:
            route: Route to update
            fitness_level: Hiker fitness level
            pack_weight_kg: Pack weight

        Returns:
            Updated route with segment times
        """
        total_time = 0.0

        for i, segment in enumerate(route.segments):
            segment.estimated_time = self.estimate_segment(
                segment, fitness_level, pack_weight_kg
            )
            total_time += segment.estimated_time

        # Update route total time
        optimistic, normal, conservative = self.estimate_route(
            route, fitness_level, pack_weight_kg
        )
        route.estimated_time = normal

        return route

    def calculate_calories(
        self,
        route: Route,
        pack_weight_kg: float = 12.0,
        body_weight_kg: float = 70.0
    ) -> int:
        """
        Calculate calories burned for a route.

        Args:
            route: Route to calculate for
            pack_weight_kg: Pack weight
            body_weight_kg: Hiker body weight

        Returns:
            Estimated calories burned
        """
        calories = self.time_estimator.estimate_calories_burned(
            route.total_distance,
            route.total_elevation_gain,
            pack_weight_kg,
            body_weight_kg
        )

        return calories

    def get_difficulty_description(self, difficulty: TrailDifficulty) -> str:
        """
        Get human-readable difficulty description.

        Args:
            difficulty: Trail difficulty

        Returns:
            Description string
        """
        descriptions = {
            TrailDifficulty.EASY: "Easy - Well-marked trails, gentle terrain",
            TrailDifficulty.MODERATE: "Moderate - Mountain trails, some steep sections",
            TrailDifficulty.DIFFICULT: "Difficult - Demanding mountain trails, steep ascents",
            TrailDifficulty.EXPERT: "Expert - Alpine terrain, requires experience and fitness"
        }
        return descriptions.get(difficulty, "Unknown difficulty")
