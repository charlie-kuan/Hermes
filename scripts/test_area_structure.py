#!/usr/bin/env python3
"""
Test script to verify the new area data structure works correctly.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from app.utils.area_loader import (
    load_areas_index,
    load_area_points,
    load_area_routes,
    load_area_full,
    load_all_areas
)


def test_areas_structure():
    """Test the new data structure loading."""
    logger.info("=" * 70)
    logger.info("Testing New Area Data Structure")
    logger.info("=" * 70)
    
    # Test 1: Load areas index
    logger.info("\n1. Testing areas index...")
    areas = load_areas_index()
    logger.info(f"   ✓ Loaded {len(areas)} areas from index")
    for area in areas:
        logger.info(f"   - {area['name']} ({area['area_id']})")
    
    if not areas:
        logger.error("   ✗ No areas found!")
        return False
    
    # Test 2: Load points for each area
    logger.info("\n2. Testing area points...")
    for area in areas:
        area_id = area['area_id']
        points = load_area_points(area_id)
        logger.info(f"   ✓ {area['name']}: {len(points)} points loaded")
        if points:
            logger.info(f"     Types: {', '.join(set(p['type'] for p in points))}")
    
    # Test 3: Load routes for each area
    logger.info("\n3. Testing area routes...")
    for area in areas:
        area_id = area['area_id']
        routes = load_area_routes(area_id)
        logger.info(f"   ✓ {area['name']}: {len(routes)} routes loaded")
        if routes:
            for route in routes[:2]:  # Show first 2 routes
                logger.info(f"     - {route['name']} ({route['days']} days, {route['difficulty']})")
    
    # Test 4: Load full area data
    logger.info("\n4. Testing full area load...")
    test_area_id = areas[0]['area_id']
    full_area = load_area_full(test_area_id)
    if full_area:
        logger.info(f"   ✓ Full data for {full_area['name']}:")
        logger.info(f"     - Base fields: area_id, name, description")
        logger.info(f"     - Points: {len(full_area['points'])}")
        logger.info(f"     - Routes: {len(full_area['recommended_routes'])}")
    else:
        logger.error(f"   ✗ Failed to load full data for {test_area_id}")
        return False
    
    # Test 5: Load all areas with complete data
    logger.info("\n5. Testing load all areas...")
    all_areas = load_all_areas()
    logger.info(f"   ✓ Loaded {len(all_areas)} complete areas")
    total_points = sum(len(a['points']) for a in all_areas)
    total_routes = sum(len(a['recommended_routes']) for a in all_areas)
    logger.info(f"   - Total points: {total_points}")
    logger.info(f"   - Total routes: {total_routes}")
    
    # Test 6: Verify data structure
    logger.info("\n6. Verifying data structure...")
    for area in all_areas:
        # Check required fields
        required = ['area_id', 'name', 'description', 'points', 'recommended_routes']
        missing = [f for f in required if f not in area]
        if missing:
            logger.error(f"   ✗ {area.get('name', 'Unknown')}: Missing fields: {missing}")
            return False
        
        # Check points structure
        for point in area['points'][:1]:  # Check first point
            point_required = ['id', 'name', 'type', 'lat', 'lon', 'elevation']
            missing = [f for f in point_required if f not in point]
            if missing:
                logger.error(f"   ✗ Point structure error: Missing {missing}")
                return False
        
        # Check routes structure
        for route in area['recommended_routes'][:1]:  # Check first route
            route_required = ['route_id', 'name', 'description', 'days', 'difficulty', 'point_sequence']
            missing = [f for f in route_required if f not in route]
            if missing:
                logger.error(f"   ✗ Route structure error: Missing {missing}")
                return False
    
    logger.success("\n   ✓ All data structures valid!")
    
    logger.info("\n" + "=" * 70)
    logger.success("✓ All tests passed!")
    logger.info("=" * 70)
    
    return True


def main():
    """Main entry point."""
    try:
        success = test_areas_structure()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
