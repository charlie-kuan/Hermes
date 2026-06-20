"""Time estimation using enhanced Naismith's Rule."""

from typing import Tuple

from app.models.domain import FitnessLevel, TrailDifficulty


class TimeEstimator:
    """Estimates hiking time using enhanced Naismith's Rule."""

    # Base speeds (km/h) by fitness level
    BASE_SPEEDS = {
        FitnessLevel.BEGINNER: 3.0,
        FitnessLevel.MODERATE: 4.0,
        FitnessLevel.EXPERT: 5.0,
    }

    # Difficulty multipliers
    DIFFICULTY_FACTORS = {
        TrailDifficulty.EASY: 1.0,
        TrailDifficulty.MODERATE: 1.15,
        TrailDifficulty.DIFFICULT: 1.35,
        TrailDifficulty.EXPERT: 1.6,
    }

    def __init__(self):
        pass

    def estimate_time(
        self,
        distance_km: float,
        elevation_gain_m: float,
        elevation_loss_m: float,
        difficulty: TrailDifficulty,
        fitness: FitnessLevel,
        pack_weight_kg: float = 12.0,
    ) -> float:
        """
        Estimate hiking time using enhanced Naismith's Rule.

        Naismith's Rule: 5 km/h + 1 hour per 600m gain
        Enhanced with: descent adjustment, difficulty, fitness, pack weight, rest breaks

        Args:
            distance_km: Horizontal distance
            elevation_gain_m: Total elevation gain
            elevation_loss_m: Total elevation loss
            difficulty: Trail difficulty
            fitness: Hiker fitness level
            pack_weight_kg: Pack weight in kg

        Returns:
            Estimated time in hours
        """
        # Base time from distance
        base_speed = self.BASE_SPEEDS[fitness]
        time_horizontal = distance_km / base_speed

        # Time for ascent: 1 hour per 400m for alpine terrain
        time_ascent = elevation_gain_m / 400.0

        # Descent adjustment (subtract time, but capped at 15% of horizontal time)
        # Rule: -10 minutes per 500m descent
        time_descent_bonus = min(
            elevation_loss_m / 500.0 / 6.0,  # Convert to hours
            time_horizontal * 0.15
        )

        # Apply difficulty factor
        difficulty_factor = self.DIFFICULTY_FACTORS[difficulty]

        # Apply pack weight penalty (2% per kg over 10kg)
        pack_penalty = 1.0 + max(0, pack_weight_kg - 10) * 0.02

        # Calculate total time
        total_time = (
            time_horizontal + time_ascent - time_descent_bonus
        ) * difficulty_factor * pack_penalty

        # Add rest breaks for longer hikes (10% extra for hikes >4 hours)
        if total_time > 4.0:
            total_time *= 1.1

        # Apply minimum only for complete routes, not individual segments
        return total_time

    def estimate_with_scenarios(
        self,
        distance_km: float,
        elevation_gain_m: float,
        elevation_loss_m: float,
        difficulty: TrailDifficulty,
        fitness: FitnessLevel,
        pack_weight_kg: float = 12.0
    ) -> Tuple[float, float, float]:
        """
        Estimate time with optimistic, normal, and conservative scenarios.

        Args:
            distance_km: Horizontal distance
            elevation_gain_m: Total elevation gain
            elevation_loss_m: Total elevation loss
            difficulty: Trail difficulty
            fitness: Hiker fitness level
            pack_weight_kg: Pack weight

        Returns:
            Tuple of (optimistic, normal, conservative) times in hours
        """
        normal = self.estimate_time(
            distance_km, elevation_gain_m, elevation_loss_m,
            difficulty, fitness, pack_weight_kg
        )

        # Optimistic: -20%
        optimistic = normal * 0.8

        # Conservative: +20%
        conservative = normal * 1.2

        return optimistic, normal, conservative

    def estimate_segment_time(
        self,
        distance_km: float,
        elevation_gain_m: float,
        elevation_loss_m: float,
        difficulty: TrailDifficulty,
        fitness: FitnessLevel,
        pack_weight_kg: float = 12.0,
        is_start: bool = False
    ) -> float:
        """
        Estimate time for a single route segment.

        Args:
            distance_km: Segment distance
            elevation_gain_m: Segment elevation gain
            elevation_loss_m: Segment elevation loss
            difficulty: Trail difficulty
            fitness: Hiker fitness level
            pack_weight_kg: Pack weight
            is_start: Whether this is the first segment (no rest break adjustment)

        Returns:
            Estimated time in hours
        """
        # Don't apply 30-minute minimum to segments (only to complete routes)
        time = self.estimate_time(
            distance_km, elevation_gain_m, elevation_loss_m,
            difficulty, fitness, pack_weight_kg,
        )

        # Don't apply rest break multiplier to individual segments
        # (it's applied at route level)
        if time > 4.0 and not is_start:
            time /= 1.1  # Remove the 10% rest break added in estimate_time

        return time

    def calculate_avg_speed(
        self,
        distance_km: float,
        elevation_gain_m: float,
        time_hours: float
    ) -> float:
        """
        Calculate average speed including elevation adjustment.

        Args:
            distance_km: Distance traveled
            elevation_gain_m: Elevation gained
            time_hours: Time taken

        Returns:
            Average speed in km/h
        """
        if time_hours == 0:
            return 0.0

        # Equivalent flat distance (Tobler's hiking function approximation)
        equivalent_distance = distance_km + (elevation_gain_m / 100.0)

        return equivalent_distance / time_hours

    def estimate_calories_burned(
        self,
        distance_km: float,
        elevation_gain_m: float,
        pack_weight_kg: float,
        body_weight_kg: float = 70.0
    ) -> int:
        """
        Estimate calories burned during hike.

        Args:
            distance_km: Distance
            elevation_gain_m: Elevation gain
            pack_weight_kg: Pack weight
            body_weight_kg: Hiker body weight

        Returns:
            Estimated calories burned
        """
        # Base metabolic rate while hiking: ~5 kcal/kg/km
        base_calories = body_weight_kg * distance_km * 5

        # Additional calories for elevation: ~10 kcal per 100m
        elevation_calories = (elevation_gain_m / 100.0) * 10

        # Pack weight adjustment: +5% per 5kg
        pack_multiplier = 1.0 + (pack_weight_kg / 5.0) * 0.05

        total = (base_calories + elevation_calories) * pack_multiplier

        return int(total)
