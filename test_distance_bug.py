"""Test if distance unit conversion is causing the bug."""

from app.core.time_estimators import TimeEstimator
from app.models.domain import FitnessLevel, TrailDifficulty

estimator = TimeEstimator()

print("=" * 60)
print("Testing Distance Unit Bug Hypothesis")
print("=" * 60)

# Simulate a 500m segment
# WRONG: passing meters as km
distance_wrong = 500  # Should be 0.5km but passing as 500km!
elevation_gain = 50
elevation_loss = 50

time_wrong = estimator.estimate_time(
    distance_wrong, elevation_gain, elevation_loss, 
    TrailDifficulty.MODERATE, FitnessLevel.MODERATE
)

print(f'\n1. Distance interpreted as {distance_wrong} KM (WRONG):')
print(f'   Estimated time: {time_wrong:.2f} hours')
print(f'   Would trigger day split: {time_wrong >= 5.6}')

# CORRECT
distance_correct = 0.5  # km
time_correct = estimator.estimate_time(
    distance_correct, elevation_gain, elevation_loss,
    TrailDifficulty.MODERATE, FitnessLevel.MODERATE
)

print(f'\n2. Distance as {distance_correct} KM (CORRECT):')
print(f'   Estimated time: {time_correct:.2f} hours')
print(f'   Would trigger day split: {time_correct >= 5.6}')

print(f'\n3. Simulation with 50 segments (each 500m):')
print(f'   If using WRONG units: {50 * time_wrong:.0f}h = {50 * time_wrong / 7:.0f} days')
print(f'   With splitting: would create {50} days (one per segment)')
print(f'   If using CORRECT units: {50 * time_correct:.0f}h = {50 * time_correct / 7:.1f} days')

print("\n" + "=" * 60)
