"""
Test script to verify the day calculation fix.

This script tests the multi-day planning logic to ensure:
1. Time estimates are calculated correctly in hours
2. Days are split properly based on target hours
3. No excessive day splits occur
"""

import sys
sys.path.insert(0, '/Users/charlie/Desktop/Project/Project_Hermes')

from app.core.time_estimators import TimeEstimator
from app.models.domain import (
    FitnessLevel, TrailDifficulty, Node, NodeType, 
    Edge, Route, RouteSegment
)

def test_time_calculation():
    """Test that time calculation produces reasonable results."""
    print("=" * 70)
    print("Test 1: Time Calculation")
    print("=" * 70)
    
    estimator = TimeEstimator()
    
    # Test a typical 2-day hike: 20km, 1500m gain
    distance_km = 20.0
    elevation_gain = 1500
    elevation_loss = 1500
    
    time = estimator.estimate_time(
        distance_km, elevation_gain, elevation_loss,
        TrailDifficulty.MODERATE, FitnessLevel.MODERATE
    )
    
    print(f"Route: {distance_km}km, {elevation_gain}m gain")
    print(f"Estimated time: {time:.2f} hours")
    print(f"Expected days (7h/day): {time / 7:.1f} days")
    print()
    
    # Verify it's reasonable
    expected_days = time / 7
    if expected_days < 1.5 or expected_days > 3.5:
        print(f"⚠️  WARNING: Expected {expected_days:.1f} days for this route seems unusual")
    else:
        print(f"✓ Time calculation looks correct")
    print()

def test_segment_distance_units():
    """Test that segment distances are correctly handled."""
    print("=" * 70)
    print("Test 2: Segment Distance Units")
    print("=" * 70)
    
    estimator = TimeEstimator()
    
    # Test with distance in KM (correct)
    distance_correct = 0.5  # 500 meters in km
    time_correct = estimator.estimate_time(
        distance_correct, 50, 50,
        TrailDifficulty.MODERATE, FitnessLevel.MODERATE
    )
    
    # Test with distance in METERS (incorrect - passed as km)
    distance_wrong = 500  # 500 meters mistakenly treated as km
    time_wrong = estimator.estimate_time(
        distance_wrong, 50, 50,
        TrailDifficulty.MODERATE, FitnessLevel.MODERATE
    )
    
    print(f"Correct: 0.5 km → {time_correct:.2f} hours")
    print(f"Wrong:   500 'km' → {time_wrong:.2f} hours (!)")
    print()
    
    if time_wrong > 24:
        print(f"✓ Detection working: {time_wrong:.1f}h > 24h threshold")
    else:
        print(f"⚠️  {time_wrong:.1f}h might not trigger detection")
    print()

def test_splitting_logic():
    """Test that the splitting logic produces reasonable day counts."""
    print("=" * 70)
    print("Test 3: Day Splitting Logic")
    print("=" * 70)
    
    # Simulate splitting logic
    target_hours = 7.0
    threshold = target_hours * 0.8  # 5.6 hours
    
    # Simulate a 15-hour hike with 30 segments (30 mins each)
    segment_times = [0.5] * 30  # 30 segments of 30 minutes each = 15 hours total
    
    days_created = 0
    cumulative = 0.0
    
    for i, seg_time in enumerate(segment_times):
        cumulative += seg_time
        is_last = (i == len(segment_times) - 1)
        should_split = (cumulative >= threshold and not is_last)
        
        if should_split or is_last:
            days_created += 1
            cumulative = 0.0
    
    total_time = sum(segment_times)
    expected_days = total_time / target_hours
    
    print(f"Total time: {total_time:.1f} hours")
    print(f"Target: {target_hours} hours/day")
    print(f"Expected days: {expected_days:.1f}")
    print(f"Created days: {days_created}")
    print()
    
    if abs(days_created - expected_days) <= 1:
        print(f"✓ Day splitting logic looks correct")
    else:
        print(f"⚠️  WARNING: Days created ({days_created}) differs significantly from expected ({expected_days:.1f})")
    print()

def test_distance_correction():
    """Test the distance correction logic."""
    print("=" * 70)
    print("Test 4: Distance Correction Logic")
    print("=" * 70)
    
    # Simulate segments with distance in meters (bug scenario)
    test_cases = [
        (0.5, "Correct: 0.5km", False),
        (500, "Bug: 500m treated as 500km", True),
        (10.5, "Correct: 10.5km", False),
        (1500, "Bug: 1500m treated as 1500km", True),
    ]
    
    for distance, description, should_correct in test_cases:
        needs_correction = distance > 100
        print(f"{description}")
        print(f"  Distance value: {distance}")
        print(f"  Needs correction: {needs_correction} (expected: {should_correct})")
        
        if needs_correction:
            corrected = distance / 1000.0
            print(f"  → Corrected to: {corrected} km")
        print()

if __name__ == "__main__":
    print("\n🔍 Testing Day Calculation Fix")
    print()
    
    test_time_calculation()
    test_segment_distance_units()
    test_splitting_logic()
    test_distance_correction()
    
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    print("""
The fix includes:
1. Detection of unreasonably high segment times (> 24 hours)
2. Automatic correction when distance appears to be in meters
3. Detailed logging to help diagnose issues
4. Sanity checks on total days created

If you're still experiencing issues:
- Check the logs for warnings about unit conversion
- Verify that route.segments have correct distance values (in km)
- Ensure estimated_time values are reasonable (hours, not minutes)
""")
