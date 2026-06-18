"""Utility functions for loading area data from refactored file structure."""

import csv
import json
from typing import List, Optional

from app.config import settings
from app.utils.logger import logger


def _derive_area_metadata(area_data: dict) -> dict:
    """Derive required API metadata fields from area points data."""
    enriched_area = area_data.copy()
    points = enriched_area.get('points', [])

    if points:
        elevations = [point['elevation'] for point in points]
        lats = [point['lat'] for point in points]
        lons = [point['lon'] for point in points]

        enriched_area['elevation_range'] = [int(min(elevations)), int(max(elevations))]
        enriched_area['bbox'] = [min(lats), min(lons), max(lats), max(lons)]
    else:
        enriched_area['elevation_range'] = [0, 0]
        enriched_area['bbox'] = None

    enriched_area.setdefault('country', '台灣')
    enriched_area.setdefault('features', [])
    enriched_area['trail_count'] = len(enriched_area.get('recommended_routes', []))
    enriched_area['peak_count'] = sum(1 for point in points if point.get('type') == 'peak')
    enriched_area['hut_count'] = sum(1 for point in points if point.get('type') == 'hut')

    return enriched_area


def load_areas_index() -> List[dict]:
    """
    Load areas index from _index.json.
    
    Returns:
        List of area metadata (area_id, name, description)
    """
    index_file = settings.data_dir / "areas" / "_index.json"
    
    if not index_file.exists():
        logger.warning(f"Areas index file not found: {index_file}")
        return []
    
    try:
        with open(index_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('areas', [])
    except Exception as e:
        logger.error(f"Error loading areas index: {e}")
        return []


def load_area_points(area_id: str) -> List[dict]:
    """
    Load points data from CSV for a specific area.
    
    Args:
        area_id: Area identifier
        
    Returns:
        List of point dictionaries
    """
    points_file = settings.data_dir / "areas" / area_id / "points.csv"
    
    if not points_file.exists():
        logger.warning(f"Points file not found for area {area_id}: {points_file}")
        return []
    
    try:
        points = []
        with open(points_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numeric fields
                point = {
                    'id': row['id'],
                    'name': row['name'],
                    'type': row['type'],
                    'lat': float(row['lat']),
                    'lon': float(row['lon']),
                    'elevation': float(row['elevation']),
                    'description': row['description'] if row['description'] else None,
                    'facilities': row['facilities'].split(';') if row['facilities'] else [],
                    'capacity': int(row['capacity']) if row['capacity'] else None
                }
                points.append(point)
        return points
    except Exception as e:
        logger.error(f"Error loading points for area {area_id}: {e}")
        return []


def load_area_routes(area_id: str) -> List[dict]:
    """
    Load routes data from CSV for a specific area.
    
    Args:
        area_id: Area identifier
        
    Returns:
        List of route dictionaries
    """
    routes_file = settings.data_dir / "areas" / area_id / "routes.csv"
    
    if not routes_file.exists():
        logger.warning(f"Routes file not found for area {area_id}: {routes_file}")
        return []
    
    try:
        routes = []
        with open(routes_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numeric and list fields
                route = {
                    'route_id': row['route_id'],
                    'name': row['name'],
                    'description': row['description'],
                    'days': int(row['days']),
                    'difficulty': row['difficulty'],
                    'estimated_distance': float(row['estimated_distance']) if row['estimated_distance'] else None,
                    'estimated_time': row['estimated_time'] if row['estimated_time'] else None,
                    'point_sequence': row['point_sequence'].split('>') if row['point_sequence'] else [],
                    'highlight': row['highlight'] if row['highlight'] else None
                }
                routes.append(route)
        return routes
    except Exception as e:
        logger.error(f"Error loading routes for area {area_id}: {e}")
        return []


def load_area_full(area_id: str) -> Optional[dict]:
    """
    Load complete area data including points and routes.
    
    Args:
        area_id: Area identifier
        
    Returns:
        Complete area dictionary or None if not found
    """
    areas = load_areas_index()
    
    # Find the area in index
    area_data = None
    for area in areas:
        if area['area_id'] == area_id:
            area_data = area.copy()
            break
    
    if not area_data:
        return None
    
    # Load associated data
    area_data['points'] = load_area_points(area_id)
    area_data['recommended_routes'] = load_area_routes(area_id)

    return _derive_area_metadata(area_data)


def load_all_areas() -> List[dict]:
    """
    Load all areas with their complete data.
    
    Returns:
        List of complete area dictionaries
    """
    areas = load_areas_index()
    
    # Load complete data for each area
    complete_areas = []
    for area in areas:
        area_id = area['area_id']
        area_data = area.copy()
        area_data['points'] = load_area_points(area_id)
        area_data['recommended_routes'] = load_area_routes(area_id)
        complete_areas.append(_derive_area_metadata(area_data))
    
    return complete_areas
