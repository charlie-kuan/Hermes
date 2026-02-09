"""Input validation utilities."""

from typing import List, Tuple


def validate_coordinates(lat: float, lon: float) -> bool:
    """Validate latitude and longitude values."""
    return -90 <= lat <= 90 and -180 <= lon <= 180


def validate_bbox(bbox: List[float]) -> bool:
    """
    Validate bounding box format and values.

    Args:
        bbox: [min_lat, min_lon, max_lat, max_lon]

    Returns:
        True if valid, False otherwise
    """
    if len(bbox) != 4:
        return False

    min_lat, min_lon, max_lat, max_lon = bbox

    if not (validate_coordinates(min_lat, min_lon) and validate_coordinates(max_lat, max_lon)):
        return False

    if min_lat >= max_lat or min_lon >= max_lon:
        return False

    return True


def validate_distance(distance: float, max_distance: float = 200.0) -> bool:
    """Validate distance value in kilometers."""
    return 0 < distance <= max_distance


def validate_elevation(elevation: float, max_elevation: float = 9000.0) -> bool:
    """Validate elevation value in meters."""
    return -500 <= elevation <= max_elevation


def validate_fitness_level(level: str) -> bool:
    """Validate fitness level value."""
    return level in ["beginner", "moderate", "expert"]
