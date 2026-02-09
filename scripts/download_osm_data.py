#!/usr/bin/env python
"""Script to download OSM data for a hiking area."""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.core.osm_processor import OSMProcessor
from app.utils.cache import graph_cache
from loguru import logger


def load_areas():
    """Load areas from areas.json."""
    areas_file = settings.data_dir / "areas.json"

    if not areas_file.exists():
        logger.error(f"Areas file not found: {areas_file}")
        return []

    with open(areas_file, 'r') as f:
        data = json.load(f)
        return data.get('areas', [])


def download_area(area_id: str, bbox: list = None):
    """
    Download OSM data for a specific area.

    Args:
        area_id: Area identifier
        bbox: Optional bounding box [min_lat, min_lon, max_lat, max_lon]
    """
    logger.info(f"Downloading OSM data for area: {area_id}")

    # Load area metadata if bbox not provided
    if bbox is None:
        areas = load_areas()
        area_data = None

        for area in areas:
            if area['area_id'] == area_id:
                area_data = area
                break

        if not area_data:
            logger.error(f"Area {area_id} not found in areas.json")
            return False

        bbox = area_data['bbox']
        logger.info(f"Using bbox from areas.json: {bbox}")

    # Download and process
    osm_processor = OSMProcessor()

    try:
        graph = osm_processor.download_trail_network(bbox, area_id)

        logger.info(
            f"Downloaded graph with {graph.number_of_nodes()} nodes "
            f"and {graph.number_of_edges()} edges"
        )

        # Save to cache
        graph_cache.save_graph(area_id, graph)
        logger.info(f"Saved graph to cache: {area_id}")

        return True

    except Exception as e:
        logger.error(f"Failed to download OSM data: {e}", exc_info=True)
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download OSM data for a hiking area"
    )
    parser.add_argument(
        "--area",
        required=True,
        help="Area ID to download"
    )
    parser.add_argument(
        "--bbox",
        help="Bounding box as 'min_lat,min_lon,max_lat,max_lon'"
    )

    args = parser.parse_args()

    # Parse bbox if provided
    bbox = None
    if args.bbox:
        try:
            bbox = [float(x) for x in args.bbox.split(',')]
            if len(bbox) != 4:
                raise ValueError("Bbox must have 4 values")
        except Exception as e:
            logger.error(f"Invalid bbox format: {e}")
            sys.exit(1)

    # Download
    success = download_area(args.area, bbox)

    if success:
        logger.info("Download completed successfully")
        sys.exit(0)
    else:
        logger.error("Download failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
