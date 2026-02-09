"""Geospatial utility functions."""

import math
from typing import List, Tuple

from geopy.distance import geodesic


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate haversine distance between two points in meters.

    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates

    Returns:
        Distance in meters
    """
    return geodesic((lat1, lon1), (lat2, lon2)).meters


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate bearing from point 1 to point 2 in degrees.

    Args:
        lat1, lon1: Start point coordinates
        lat2, lon2: End point coordinates

    Returns:
        Bearing in degrees (0-360)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)

    x = math.sin(delta_lon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)

    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def point_to_line_distance(
    point: Tuple[float, float],
    line_start: Tuple[float, float],
    line_end: Tuple[float, float]
) -> float:
    """
    Calculate perpendicular distance from a point to a line segment.

    Args:
        point: (lat, lon) of the point
        line_start: (lat, lon) of line segment start
        line_end: (lat, lon) of line segment end

    Returns:
        Distance in meters
    """
    # Calculate distances
    d_start = haversine_distance(point[0], point[1], line_start[0], line_start[1])
    d_end = haversine_distance(point[0], point[1], line_end[0], line_end[1])
    d_line = haversine_distance(line_start[0], line_start[1], line_end[0], line_end[1])

    if d_line == 0:
        return d_start

    # Use Heron's formula for perpendicular distance
    s = (d_start + d_end + d_line) / 2
    area = math.sqrt(max(0, s * (s - d_start) * (s - d_end) * (s - d_line)))
    perpendicular = 2 * area / d_line if d_line > 0 else 0

    return perpendicular


def find_nearest_point(
    target_lat: float,
    target_lon: float,
    points: List[Tuple[float, float, str]]
) -> Tuple[str, float]:
    """
    Find the nearest point from a list to a target location.

    Args:
        target_lat, target_lon: Target coordinates
        points: List of (lat, lon, id) tuples

    Returns:
        Tuple of (nearest_point_id, distance_in_meters)
    """
    if not points:
        raise ValueError("Points list cannot be empty")

    nearest_id = None
    min_distance = float('inf')

    for lat, lon, point_id in points:
        distance = haversine_distance(target_lat, target_lon, lat, lon)
        if distance < min_distance:
            min_distance = distance
            nearest_id = point_id

    return nearest_id, min_distance


def interpolate_elevation(
    lat: float,
    lon: float,
    point1: Tuple[float, float, float],
    point2: Tuple[float, float, float]
) -> float:
    """
    Interpolate elevation at a point between two points with known elevations.

    Args:
        lat, lon: Target point coordinates
        point1: (lat, lon, elevation) of first reference point
        point2: (lat, lon, elevation) of second reference point

    Returns:
        Interpolated elevation in meters
    """
    d1 = haversine_distance(lat, lon, point1[0], point1[1])
    d2 = haversine_distance(lat, lon, point2[0], point2[1])
    total = d1 + d2

    if total == 0:
        return point1[2]

    # Linear interpolation weighted by inverse distance
    weight1 = d2 / total
    weight2 = d1 / total

    return weight1 * point1[2] + weight2 * point2[2]


def calculate_bbox_area(bbox: List[float]) -> float:
    """
    Calculate approximate area of a bounding box in square kilometers.

    Args:
        bbox: [min_lat, min_lon, max_lat, max_lon]

    Returns:
        Area in square kilometers
    """
    min_lat, min_lon, max_lat, max_lon = bbox

    # Calculate distances
    width = haversine_distance(min_lat, min_lon, min_lat, max_lon) / 1000
    height = haversine_distance(min_lat, min_lon, max_lat, min_lon) / 1000

    return width * height
