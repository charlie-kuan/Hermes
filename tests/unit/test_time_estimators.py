"""Tests for time estimation algorithms."""

import pytest

from app.core.time_estimators import TimeEstimator
from app.models.domain import FitnessLevel, TrailDifficulty


class TestTimeEstimator:
    """Test TimeEstimator class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.estimator = TimeEstimator()

    def test_basic_estimation(self):
        """Test basic time estimation."""
        # 10 km flat trail, moderate difficulty
        time = self.estimator.estimate_time(
            distance_km=10.0,
            elevation_gain_m=0.0,
            elevation_loss_m=0.0,
            difficulty=TrailDifficulty.MODERATE,
            fitness=FitnessLevel.MODERATE,
            pack_weight_kg=12.0
        )

        # Should be around 2 hours (10km / 5 km/h)
        assert 1.8 <= time <= 2.5

    def test_elevation_gain(self):
        """Test elevation gain increases time."""
        # Same distance, with elevation
        time_flat = self.estimator.estimate_time(
            distance_km=10.0,
            elevation_gain_m=0.0,
            elevation_loss_m=0.0,
            difficulty=TrailDifficulty.EASY,
            fitness=FitnessLevel.MODERATE,
            pack_weight_kg=12.0
        )

        time_climb = self.estimator.estimate_time(
            distance_km=10.0,
            elevation_gain_m=600.0,  # +1 hour by Naismith
            elevation_loss_m=0.0,
            difficulty=TrailDifficulty.EASY,
            fitness=FitnessLevel.MODERATE,
            pack_weight_kg=12.0
        )

        # Climbing should take more time
        assert time_climb > time_flat
        # Should be roughly 1 hour more
        assert abs((time_climb - time_flat) - 1.0) < 0.3

    def test_fitness_level_impact(self):
        """Test fitness level affects time."""
        params = {
            "distance_km": 10.0,
            "elevation_gain_m": 300.0,
            "elevation_loss_m": 0.0,
            "difficulty": TrailDifficulty.MODERATE,
            "pack_weight_kg": 12.0
        }

        beginner_time = self.estimator.estimate_time(
            **params, fitness=FitnessLevel.BEGINNER
        )
        moderate_time = self.estimator.estimate_time(
            **params, fitness=FitnessLevel.MODERATE
        )
        expert_time = self.estimator.estimate_time(
            **params, fitness=FitnessLevel.EXPERT
        )

        # Beginner should be slowest, expert fastest
        assert beginner_time > moderate_time > expert_time

    def test_difficulty_impact(self):
        """Test difficulty affects time."""
        params = {
            "distance_km": 10.0,
            "elevation_gain_m": 300.0,
            "elevation_loss_m": 0.0,
            "fitness": FitnessLevel.MODERATE,
            "pack_weight_kg": 12.0
        }

        easy_time = self.estimator.estimate_time(
            **params, difficulty=TrailDifficulty.EASY
        )
        difficult_time = self.estimator.estimate_time(
            **params, difficulty=TrailDifficulty.DIFFICULT
        )
        expert_time = self.estimator.estimate_time(
            **params, difficulty=TrailDifficulty.EXPERT
        )

        # More difficult should take longer
        assert expert_time > difficult_time > easy_time

    def test_pack_weight_penalty(self):
        """Test heavier pack increases time."""
        params = {
            "distance_km": 10.0,
            "elevation_gain_m": 300.0,
            "elevation_loss_m": 0.0,
            "difficulty": TrailDifficulty.MODERATE,
            "fitness": FitnessLevel.MODERATE
        }

        light_time = self.estimator.estimate_time(**params, pack_weight_kg=10.0)
        heavy_time = self.estimator.estimate_time(**params, pack_weight_kg=20.0)

        # Heavier pack should take longer
        assert heavy_time > light_time

    def test_scenarios(self):
        """Test optimistic/normal/conservative scenarios."""
        optimistic, normal, conservative = self.estimator.estimate_with_scenarios(
            distance_km=10.0,
            elevation_gain_m=500.0,
            elevation_loss_m=200.0,
            difficulty=TrailDifficulty.MODERATE,
            fitness=FitnessLevel.MODERATE,
            pack_weight_kg=12.0
        )

        # Optimistic should be 20% faster
        assert abs(optimistic / normal - 0.8) < 0.01

        # Conservative should be 20% slower
        assert abs(conservative / normal - 1.2) < 0.01

    def test_minimum_time(self):
        """Test minimum time is enforced."""
        # Very short route
        time = self.estimator.estimate_time(
            distance_km=0.1,
            elevation_gain_m=0.0,
            elevation_loss_m=0.0,
            difficulty=TrailDifficulty.EASY,
            fitness=FitnessLevel.EXPERT,
            pack_weight_kg=5.0
        )

        # Should not be less than 30 minutes
        assert time >= 0.5
