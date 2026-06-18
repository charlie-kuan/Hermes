#!/usr/bin/env python3
"""
Example script: Enrich trail graphs with GPS trace data.

This script demonstrates how to use GPS traces to improve route popularity scoring.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from app.services.graph_service import GraphService
from app.config import settings
from app.utils.area_loader import load_area_full


def main():
    """Enrich graph with GPS traces."""
    
    logger.info("GPS Trace Enrichment Example")
    logger.info("=" * 60)
    
    # Initialize service
    graph_service = GraphService()
    
    # Example 1: Load existing graph and enrich with GPS traces
    area_id = "yushan"
    
    logger.info(f"\n1. Loading graph for {area_id}")
    
    try:
        # Get or build graph without explicit bbox:
        # 1) auto-calculate from area routes if available
        # 2) fallback to GPS-trace-based graph if bbox is unavailable
        area_data = load_area_full(area_id)
        graph = graph_service.get_or_build_graph(area_id, area_data=area_data)
        
        logger.info(f"   Graph loaded: {graph.number_of_nodes()} nodes, "
                   f"{graph.number_of_edges()} edges")
        
        # Get initial stats
        stats_before = graph_service.get_graph_stats(graph)
        logger.info(f"   Total distance: {stats_before['total_distance_km']:.1f} km")
        
        # Show some initial popularity scores
        logger.info("\n2. Current popularity scores (OSM-based):")
        edge_count = 0
        total_popularity = 0.0
        
        for u, v, key, data in graph.edges(keys=True, data=True):
            edge = data['data']
            total_popularity += edge.popularity_score
            edge_count += 1
            
            if edge_count <= 5:  # Show first 5
                logger.info(f"   Edge {u[:8]}→{v[:8]}: {edge.popularity_score:.2f}")
        
        avg_popularity = total_popularity / edge_count if edge_count > 0 else 0
        logger.info(f"   Average popularity: {avg_popularity:.2f}")
        
        # Example 2: Enrich with GPS traces
        logger.info("\n3. Enriching with GPS traces...")
        logger.info("   Place your GPS trace files (.gpx or .geojson) in:")
        logger.info(f"   {settings.data_dir}/gps_traces/{area_id}/")
        
        gps_trace_dir = Path(settings.data_dir) / "gps_traces" / area_id
        
        if not gps_trace_dir.exists():
            logger.info(f"\n   Creating directory: {gps_trace_dir}")
            gps_trace_dir.mkdir(parents=True, exist_ok=True)
            logger.info("\n   ⚠️  Add GPS trace files and run this script again.")
            logger.info("\n   You can get GPS traces from:")
            logger.info("   - OpenStreetMap GPS traces: https://www.openstreetmap.org/traces")
            logger.info("   - Your own GPX files from hiking apps")
            logger.info("   - Exported routes from Strava, Garmin, etc.")
            return
        
        # Check if there are any trace files
        gpx_files = list(gps_trace_dir.glob("*.gpx"))
        geojson_files = list(gps_trace_dir.glob("*.geojson")) + list(gps_trace_dir.glob("*.json"))
        
        if not gpx_files and not geojson_files:
            logger.warning(f"\n   No GPS trace files found in {gps_trace_dir}")
            logger.info("\n   Add .gpx or .geojson files to this directory and try again.")
            return
        
        logger.info(f"   Found {len(gpx_files)} GPX files, {len(geojson_files)} GeoJSON files")
        
        # Enrich graph with different blend factors
        for blend_factor in [0.3, 0.5, 0.7]:
            logger.info(f"\n   Enriching with blend factor = {blend_factor}")
            logger.info(f"   (0 = pure OSM, 1 = pure GPS traces)")
            
            # Make a copy for testing
            import copy
            test_graph = copy.deepcopy(graph)
            
            graph_service.enrich_with_gps_traces(
                test_graph,
                area_id,
                gps_trace_dir=gps_trace_dir,
                blend_factor=blend_factor
            )
            
            # Calculate new average
            total_popularity_new = 0.0
            edge_count = 0
            
            for u, v, key, data in test_graph.edges(keys=True, data=True):
                edge = data['data']
                total_popularity_new += edge.popularity_score
                edge_count += 1
            
            avg_popularity_new = total_popularity_new / edge_count if edge_count > 0 else 0
            logger.info(f"      New average popularity: {avg_popularity_new:.2f}")
        
        logger.info("\n4. How to use in route planning:")
        logger.info("   - Higher blend_factor = more influence from actual GPS traces")
        logger.info("   - Popular trails (more GPS traces) get higher scores")
        logger.info("   - Set cost_function preference 'popularity' > 0 to prefer popular trails")
        logger.info("   - Example: preferences={'popularity': 0.5} in route planning")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
