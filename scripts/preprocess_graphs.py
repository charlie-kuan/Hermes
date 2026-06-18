#!/usr/bin/env python
"""Script to preprocess and cache graphs for hiking areas."""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.graph_service import GraphService
from app.utils.area_loader import load_all_areas, load_area_full
from loguru import logger


def load_areas():
    """Load areas from data/areas structure."""
    return load_all_areas()


def preprocess_area(area_id: str):
    """
    Preprocess graph for a specific area.

    Args:
        area_id: Area identifier
    """
    logger.info(f"Preprocessing area: {area_id}")

    # Load area metadata
    area_data = load_area_full(area_id)

    if not area_data:
        logger.error(f"Area {area_id} not found in data/areas")
        return False

    # Build graph - bbox auto-calculated from routes
    graph_service = GraphService()

    try:
        graph = graph_service.get_or_build_graph(area_id, area_data=area_data)

        # Get stats
        stats = graph_service.get_graph_stats(graph)

        logger.info(f"Graph statistics for {area_id}:")
        logger.info(f"  Nodes: {stats['total_nodes']}")
        logger.info(f"  Edges: {stats['total_edges']}")
        logger.info(f"  Total distance: {stats['total_distance_km']:.1f} km")
        logger.info(f"  Node types: {stats['node_counts']}")
        logger.info(f"  Connected: {stats['is_connected']}")

        return True

    except Exception as e:
        logger.error(f"Failed to preprocess area: {e}", exc_info=True)
        return False


def preprocess_all():
    """Preprocess all areas."""
    areas = load_areas()

    if not areas:
        logger.warning("No areas found to preprocess")
        return

    logger.info(f"Preprocessing {len(areas)} areas")

    success_count = 0
    fail_count = 0

    for area in areas:
        area_id = area['area_id']

        if preprocess_area(area_id):
            success_count += 1
        else:
            fail_count += 1

    logger.info(f"Preprocessing complete: {success_count} succeeded, {fail_count} failed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Preprocess and cache graphs for hiking areas"
    )
    parser.add_argument(
        "--area",
        help="Specific area ID to preprocess (omit to process all)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Preprocess all areas"
    )

    args = parser.parse_args()

    if args.all or (not args.area):
        preprocess_all()
    elif args.area:
        success = preprocess_area(args.area)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
