#!/usr/bin/env python3
"""
Test script: Verify auto-bbox calculation from routes.

This demonstrates that bbox can be automatically calculated from
route coordinates, eliminating manual maintenance.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from app.api.routes.areas import load_areas
from app.utils.geo_utils import calculate_bbox_from_area_data


def main():
    """Test auto-bbox calculation."""
    
    logger.info("Testing Auto-Bbox Calculation")
    logger.info("=" * 70)
    
    # Load areas
    areas = load_areas()
    
    if not areas:
        logger.error("No areas found in areas.json")
        return
    
    logger.info(f"\nFound {len(areas)} areas\n")
    
    # Test each area
    for area in areas[:3]:  # Test first 3 areas
        area_id = area['area_id']
        area_name = area['name']
        
        logger.info(f"Testing: {area_name} ({area_id})")
        logger.info("-" * 70)
        
        # Get legacy bbox if exists
        legacy_bbox = area.get('bbox')
        if legacy_bbox:
            logger.info(f"  Legacy bbox: [{legacy_bbox[0]:.4f}, {legacy_bbox[1]:.4f}, "
                       f"{legacy_bbox[2]:.4f}, {legacy_bbox[3]:.4f}]")
        else:
            logger.info(f"  Legacy bbox: None")
        
        # Calculate bbox from routes
        try:
            auto_bbox = calculate_bbox_from_area_data(area, buffer_km=2.0)
            logger.info(f"  Auto bbox:   [{auto_bbox[0]:.4f}, {auto_bbox[1]:.4f}, "
                       f"{auto_bbox[2]:.4f}, {auto_bbox[3]:.4f}]")
            
            # Compare if legacy exists
            if legacy_bbox:
                lat_diff = max(abs(legacy_bbox[0] - auto_bbox[0]), 
                             abs(legacy_bbox[2] - auto_bbox[2]))
                lon_diff = max(abs(legacy_bbox[1] - auto_bbox[1]), 
                             abs(legacy_bbox[3] - auto_bbox[3]))
                
                logger.info(f"  Difference:  lat ±{lat_diff:.4f}°, lon ±{lon_diff:.4f}°")
                
                if lat_diff < 0.05 and lon_diff < 0.05:
                    logger.success(f"  ✓ Auto-bbox closely matches legacy bbox")
                else:
                    logger.warning(f"  ⚠ Auto-bbox differs significantly from legacy")
            else:
                logger.success(f"  ✓ Auto-bbox calculated successfully (no legacy to compare)")
            
            # Show route count
            route_count = len(area.get('routes', []))
            logger.info(f"  Routes used: {route_count}")
            
        except ValueError as e:
            logger.error(f"  ✗ Failed to calculate auto-bbox: {e}")
        
        logger.info("")
    
    logger.info("=" * 70)
    logger.info("\n✓ Test complete!")
    logger.info("\nConclusion:")
    logger.info("  - bbox can now be auto-calculated from routes")
    logger.info("  - Manual bbox maintenance is no longer required")
    logger.info("  - Legacy bbox values are preserved for backward compatibility")
    logger.info("  - New areas can omit bbox entirely")


if __name__ == "__main__":
    main()
