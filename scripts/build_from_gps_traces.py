#!/usr/bin/env python3
"""
Example script: Build trail graph directly from GPS traces.

This demonstrates how to use GPS traces as the PRIMARY data source
instead of relying on OSM trail data, which may be incomplete.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from app.services.graph_service import GraphService
from app.config import settings


def main():
    """Build graph from GPS traces."""
    
    logger.info("Building Trail Graph from GPS Traces")
    logger.info("=" * 60)
    
    # Initialize service
    graph_service = GraphService()
    
    # Example area
    area_id = "yushan"
    
    logger.info(f"\n1. Building graph from GPS traces for {area_id}")
    logger.info("   This is useful when OSM trail data is insufficient.")
    
    gps_trace_dir = Path(settings.data_dir) / "gps_traces" / area_id
    
    if not gps_trace_dir.exists():
        logger.warning(f"\n   GPS trace directory not found: {gps_trace_dir}")
        logger.info("\n   Creating directory and adding sample guidance...")
        gps_trace_dir.mkdir(parents=True, exist_ok=True)
        
        readme_content = """# GPS Traces for Graph Building

## Purpose

This directory contains GPS traces used to build the trail network graph.
When OSM data is insufficient, GPS traces can be the PRIMARY data source.

## What to Add

1. **GPX files** from hiking apps (AllTrails, Komoot, Gaia GPS, etc.)
2. **GeoJSON files** with LineString features
3. Multiple traces covering the area from different angles

## Minimum Requirements

- At least 10-20 traces for basic coverage
- More traces = better graph quality
- Traces should overlap to identify intersections

## Usage

```bash
python scripts/build_from_gps_traces.py
```

The system will:
1. Load all GPS traces from this directory
2. Find intersection points between traces
3. Create nodes at intersections and endpoints
4. Create edges between nodes
5. Assign popularity based on trace frequency
"""
        
        readme_path = gps_trace_dir / "README.md"
        with open(readme_path, 'w') as f:
            f.write(readme_content)
        
        logger.info(f"\n   Created {readme_path}")
        logger.info("\n   Add your GPS trace files (.gpx or .geojson) and run again.")
        return
    
    # Check for trace files
    gpx_files = list(gps_trace_dir.glob("*.gpx"))
    geojson_files = list(gps_trace_dir.glob("*.geojson")) + list(gps_trace_dir.glob("*.json"))
    
    if not gpx_files and not geojson_files:
        logger.warning(f"\n   No GPS trace files found in {gps_trace_dir}")
        logger.info("\n   Add .gpx or .geojson files to this directory and try again.")
        return
    
    logger.info(f"   Found {len(gpx_files)} GPX files, {len(geojson_files)} GeoJSON files")
    
    try:
        # Build graph from GPS traces
        logger.info("\n2. Building graph...")
        graph = graph_service.build_graph_from_gps_traces(
            area_id=area_id,
            simplify_tolerance=0.0001,  # ~11 meters, reduces GPS noise
            intersection_threshold=50.0  # 50 meters to identify intersections
        )
        
        logger.info(f"\n   Graph built successfully!")
        logger.info(f"   - Nodes: {graph.number_of_nodes()}")
        logger.info(f"   - Edges: {graph.number_of_edges()}")
        
        # Show edge statistics
        logger.info("\n3. Edge statistics (by GPS trace frequency):")
        
        from collections import defaultdict
        trace_count_distribution = defaultdict(int)
        
        for u, v, key, data in graph.edges(keys=True, data=True):
            edge = data['data']
            trace_count = edge.gps_trace_count
            trace_count_distribution[trace_count] += 1
        
        for count in sorted(trace_count_distribution.keys()):
            num_edges = trace_count_distribution[count]
            logger.info(f"   - {num_edges} edges with {count} traces")
        
        # Calculate total distance
        total_distance = 0.0
        for u, v, key, data in graph.edges(keys=True, data=True):
            edge = data['data']
            total_distance += edge.distance
        
        logger.info(f"\n   Total trail distance: {total_distance / 1000:.1f} km")
        
        # Example of finding/creating nodes
        logger.info("\n4. Demo: Find or create node at arbitrary point")
        
        # Get a sample edge
        if graph.number_of_edges() > 0:
            u, v, key = list(graph.edges(keys=True))[0]
            edge = graph.edges[u, v, key]['data']
            
            if edge.geometry and len(edge.geometry) >= 2:
                # Pick point in middle of edge
                mid_lat = (edge.geometry[0][0] + edge.geometry[1][0]) / 2
                mid_lon = (edge.geometry[0][1] + edge.geometry[1][1]) / 2
                
                logger.info(f"   Trying to find node at ({mid_lat:.5f}, {mid_lon:.5f})")
                logger.info(f"   This point is on edge {u[:8]}...→{v[:8]}...")
                
                # This will split the edge and create a new node
                node_id = graph_service.find_or_create_node_at_point(
                    graph, mid_lat, mid_lon, 
                    max_distance=100.0,
                    split_edges=True
                )
                
                if node_id:
                    logger.info(f"   ✓ Created/found node: {node_id}")
                    logger.info(f"   Graph now has {graph.number_of_nodes()} nodes "
                               f"(+1 from splitting)")
        
        logger.info("\n5. Benefits of GPS trace-based graphs:")
        logger.info("   ✓ Includes trails not in OSM")
        logger.info("   ✓ Reflects actual hiking routes")
        logger.info("   ✓ Popularity based on real usage")
        logger.info("   ✓ Can start/end routes at arbitrary points")
        
        logger.info("\n6. Usage in routing:")
        logger.info("   # Load GPS-based graph")
        logger.info("   graph = graph_service.get_or_build_graph('yushan')")
        logger.info("   ")
        logger.info("   # Find node at user's GPS location (will split edge if needed)")
        logger.info("   start_node = graph_service.find_or_create_node_at_point(")
        logger.info("       graph, user_lat, user_lon, split_edges=True)")
        logger.info("   ")
        logger.info("   # Plan route")
        logger.info("   route = routing_service.plan_route(")
        logger.info("       graph, start_node, end_node)")
        
    except Exception as e:
        logger.error(f"Failed to build graph: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
