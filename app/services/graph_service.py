"""Graph management service."""

from pathlib import Path
from typing import List, Optional

import networkx as nx
from loguru import logger

from app.config import settings
from app.core.osm_processor import OSMProcessor
from app.core.gps_trace_processor import GPSTraceProcessor
from app.exceptions import GraphNotFoundError, InvalidAreaError
from app.models.domain import Node
from app.utils.cache import graph_cache
from app.utils.geo_utils import haversine_distance


class GraphService:
    """Manages trail network graphs for different hiking areas."""

    def __init__(self):
        self.osm_processor = OSMProcessor()
        self.gps_trace_processor = GPSTraceProcessor()
        self.loaded_graphs = {}  # In-memory cache

    def get_or_build_graph(self, area_id: str, bbox: Optional[List[float]] = None) -> nx.MultiDiGraph:
        """
        Get graph for an area, building it if necessary.

        Args:
            area_id: Area identifier
            bbox: Optional bounding box [min_lat, min_lon, max_lat, max_lon]

        Returns:
            NetworkX MultiDiGraph

        Raises:
            GraphNotFoundError: If graph not found and bbox not provided
        """
        # Check in-memory cache
        if area_id in self.loaded_graphs:
            logger.debug(f"Using in-memory cached graph for {area_id}")
            return self.loaded_graphs[area_id]

        # Check disk cache
        cached_graph = graph_cache.load_graph(area_id)
        if cached_graph is not None:
            self.loaded_graphs[area_id] = cached_graph
            return cached_graph

        # Build new graph
        if bbox is None:
            raise GraphNotFoundError(f"No cached graph for {area_id} and no bbox provided to build one")

        logger.info(f"Building new graph for area: {area_id}")
        graph = self.osm_processor.download_trail_network(bbox, area_id)

        # Cache the graph
        graph_cache.save_graph(area_id, graph)
        self.loaded_graphs[area_id] = graph

        return graph

    def find_nearest_node(
        self,
        graph: nx.MultiDiGraph,
        lat: float,
        lon: float,
        max_distance: float = 2000.0
    ) -> Optional[str]:
        """
        Find nearest node in graph to given coordinates.

        Args:
            graph: Trail network graph
            lat, lon: Target coordinates
            max_distance: Maximum distance in meters (default 2km)

        Returns:
            Node ID or None if no node within max_distance
        """
        from app.utils.geo_utils import haversine_distance
        from loguru import logger

        min_dist = float('inf')
        nearest = None

        for node_id, data in graph.nodes(data=True):
            node: Node = data['data']
            dist = haversine_distance(lat, lon, node.lat, node.lon)

            if dist < min_dist:
                min_dist = dist
                nearest = node_id

        if min_dist > max_distance:
            logger.warning(
                f"Nearest node is {min_dist:.0f}m away at ({lat:.5f}, {lon:.5f}), "
                f"exceeds max distance of {max_distance:.0f}m"
            )
            return None

        return nearest

    def get_nodes_by_type(
        self,
        graph: nx.MultiDiGraph,
        node_types: List[str]
    ) -> List[Node]:
        """
        Get all nodes of specific types.

        Args:
            graph: Trail network graph
            node_types: List of node type strings (e.g., ['peak', 'hut'])

        Returns:
            List of matching nodes
        """
        from app.models.domain import NodeType

        # Convert strings to NodeType enums
        target_types = []
        for nt in node_types:
            try:
                target_types.append(NodeType(nt))
            except ValueError:
                logger.warning(f"Unknown node type: {nt}")

        matching_nodes = []
        for node_id, data in graph.nodes(data=True):
            node: Node = data['data']
            if node.node_type in target_types:
                matching_nodes.append(node)

        return matching_nodes

    def get_node(self, graph: nx.MultiDiGraph, node_id: str) -> Optional[Node]:
        """
        Get a specific node by ID.

        Args:
            graph: Trail network graph
            node_id: Node identifier

        Returns:
            Node object or None if not found
        """
        if node_id in graph.nodes:
            return graph.nodes[node_id]['data']
        return None

    def clear_cache(self, area_id: Optional[str] = None) -> None:
        """
        Clear cached graphs.

        Args:
            area_id: Specific area to clear, or None for all
        """
        if area_id:
            if area_id in self.loaded_graphs:
                del self.loaded_graphs[area_id]
            graph_cache.clear_cache(area_id)
        else:
            self.loaded_graphs.clear()
            graph_cache.clear_cache()

        logger.info(f"Cleared graph cache for {area_id or 'all areas'}")

    def get_graph_stats(self, graph: nx.MultiDiGraph) -> dict:
        """
        Get statistics about a graph.

        Args:
            graph: Trail network graph

        Returns:
            Dictionary of statistics
        """
        from app.models.domain import NodeType

        # Count nodes by type
        node_counts = {}
        for node_id, data in graph.nodes(data=True):
            node: Node = data['data']
            node_type = node.node_type.value
            node_counts[node_type] = node_counts.get(node_type, 0) + 1

        # Calculate total distance
        total_distance = 0
        for u, v, key, data in graph.edges(keys=True, data=True):
            edge = data['data']
            total_distance += edge.distance

        return {
            'total_nodes': graph.number_of_nodes(),
            'total_edges': graph.number_of_edges(),
            'total_distance_km': total_distance / 1000.0,
            'node_counts': node_counts,
            'is_connected': nx.is_weakly_connected(graph) if graph.number_of_nodes() > 0 else False
        }

    def enrich_with_gps_traces(
        self,
        graph: nx.MultiDiGraph,
        area_id: str,
        gps_trace_dir: Optional[Path] = None,
        blend_factor: float = 0.7
    ) -> None:
        """
        Enrich graph with GPS trace-based popularity data.

        Args:
            graph: Trail network graph to enrich
            area_id: Area identifier for finding trace files
            gps_trace_dir: Directory containing GPS trace files (GPX or GeoJSON)
            blend_factor: Weight for GPS trace data (0-1, higher = more GPS influence)
        """
        if gps_trace_dir is None:
            gps_trace_dir = Path(settings.data_dir) / "gps_traces" / area_id

        if not gps_trace_dir.exists():
            logger.warning(f"GPS trace directory not found: {gps_trace_dir}")
            return

        # Load GPS traces from available files
        traces = []

        # Load GPX files
        gpx_files = list(gps_trace_dir.glob("*.gpx"))
        if gpx_files:
            traces.extend(self.gps_trace_processor.load_gps_traces_from_gpx_files(gps_trace_dir))

        # Load GeoJSON files  
        geojson_files = list(gps_trace_dir.glob("*.geojson")) + list(gps_trace_dir.glob("*.json"))
        for geojson_file in geojson_files:
            traces.extend(self.gps_trace_processor.load_gps_traces_from_geojson(geojson_file))

        if not traces:
            logger.warning(f"No GPS traces found in {gps_trace_dir}")
            return

        # Enrich graph with trace data
        logger.info(f"Enriching graph with {len(traces)} GPS traces (blend: {blend_factor})")
        self.gps_trace_processor.enrich_graph_with_trace_popularity(
            graph, traces, blend_factor
        )

        # Update cache with enriched graph
        graph_cache.save_graph(area_id, graph)
        logger.info(f"Updated cached graph for {area_id} with GPS trace popularity")

    def build_graph_from_gps_traces(
        self,
        area_id: str,
        gps_trace_dir: Optional[Path] = None,
        simplify_tolerance: float = 0.0001,
        intersection_threshold: float = 50.0
    ) -> nx.MultiDiGraph:
        """
        Build a trail network graph directly from GPS traces.
        
        This is useful when OSM data is insufficient or unavailable.
        The graph will be built entirely from GPS trace data.
        
        Args:
            area_id: Area identifier
            gps_trace_dir: Directory containing GPS trace files
            simplify_tolerance: Tolerance for trace simplification
            intersection_threshold: Distance threshold for finding intersections
            
        Returns:
            NetworkX MultiDiGraph built from GPS traces
        """
        if gps_trace_dir is None:
            gps_trace_dir = Path(settings.data_dir) / "gps_traces" / area_id

        if not gps_trace_dir.exists():
            raise FileNotFoundError(f"GPS trace directory not found: {gps_trace_dir}")

        # Load GPS traces
        traces = []
        
        # Load GPX files
        gpx_files = list(gps_trace_dir.glob("*.gpx"))
        if gpx_files:
            traces.extend(self.gps_trace_processor.load_gps_traces_from_gpx_files(gps_trace_dir))

        # Load GeoJSON files
        geojson_files = list(gps_trace_dir.glob("*.geojson")) + list(gps_trace_dir.glob("*.json"))
        for geojson_file in geojson_files:
            traces.extend(self.gps_trace_processor.load_gps_traces_from_geojson(geojson_file))

        if not traces:
            raise ValueError(f"No GPS traces found in {gps_trace_dir}")

        logger.info(f"Building graph from {len(traces)} GPS traces for area {area_id}")
        
        # Build graph from traces
        graph = self.gps_trace_processor.build_graph_from_gps_traces(
            traces,
            simplify_tolerance=simplify_tolerance,
            intersection_threshold=intersection_threshold
        )
        
        # Enrich with elevation data if available
        try:
            self.osm_processor._enrich_elevations(graph)
            self.osm_processor._calculate_edge_metrics(graph)
        except Exception as e:
            logger.warning(f"Could not enrich elevation data: {e}")
        
        # Cache the graph
        graph_cache.save_graph(area_id, graph)
        self.loaded_graphs[area_id] = graph
        
        logger.info(f"Built and cached GPS-based graph for {area_id}")
        return graph

    def find_or_create_node_at_point(
        self,
        graph: nx.MultiDiGraph,
        lat: float,
        lon: float,
        max_distance: float = 100.0,
        split_edges: bool = True
    ) -> Optional[str]:
        """
        Find nearest node to a point, or create one by splitting an edge if needed.
        
        This allows users to start/end routes at arbitrary points, not just
        at existing nodes. If the point is close to an edge but far from nodes,
        the edge will be split at that point.
        
        Args:
            graph: Trail network graph
            lat: Latitude
            lon: Longitude
            max_distance: Maximum distance in meters to search
            split_edges: If True, will split edges to create nodes at arbitrary points
            
        Returns:
            Node ID, or None if no suitable location found
        """
        # First, try to find existing node nearby
        nearest_node_id = self.find_nearest_node(graph, lat, lon, max_distance)
        
        if nearest_node_id:
            node: Node = graph.nodes[nearest_node_id]['data']
            dist = haversine_distance(lat, lon, node.lat, node.lon)
            
            # If very close to existing node, use it
            if dist < 20.0:  # Within 20 meters
                logger.info(f"Using existing node {nearest_node_id} ({dist:.1f}m away)")
                return nearest_node_id
        
        # If allowed, try to split an edge
        if split_edges:
            nearest_edge = self.gps_trace_processor.find_nearest_edge(
                graph, lat, lon, max_distance
            )
            
            if nearest_edge:
                source_id, target_id, key, distance = nearest_edge
                logger.info(f"Found edge {source_id} -> {target_id} at {distance:.1f}m from point")
                
                # Split the edge at this point
                new_node_id = self.gps_trace_processor.split_edge_at_point(
                    graph, (source_id, target_id, key), lat, lon
                )
                
                return new_node_id
        
        # No suitable node or edge found
        logger.warning(f"No node or edge found within {max_distance}m of ({lat:.5f}, {lon:.5f})")
        return None

    def merge_graphs(
        self,
        osm_graph: nx.MultiDiGraph,
        gps_graph: nx.MultiDiGraph,
        merge_threshold: float = 30.0
    ) -> nx.MultiDiGraph:
        """
        Merge an OSM-based graph with a GPS trace-based graph.
        
        This creates a hybrid graph that includes both official trails (from OSM)
        and popular routes revealed by GPS traces.
        
        Args:
            osm_graph: Graph built from OSM data
            gps_graph: Graph built from GPS traces
            merge_threshold: Distance threshold for merging nearby nodes (meters)
            
        Returns:
            Merged graph
        """
        logger.info("Merging OSM graph and GPS trace graph")
        
        # Start with OSM graph as base
        merged = osm_graph.copy()
        
        # Map GPS nodes to OSM nodes if they're close
        gps_to_osm = {}  # GPS node ID -> OSM node ID
        
        for gps_node_id, gps_data in gps_graph.nodes(data=True):
            gps_node: Node = gps_data['data']
            
            # Find nearest OSM node
            nearest_osm_id = self.find_nearest_node(
                osm_graph, gps_node.lat, gps_node.lon, merge_threshold
            )
            
            if nearest_osm_id:
                # Use existing OSM node
                gps_to_osm[gps_node_id] = nearest_osm_id
            else:
                # Add new node from GPS graph
                merged.add_node(gps_node_id, data=gps_node)
                gps_to_osm[gps_node_id] = gps_node_id
        
        # Add edges from GPS graph
        added_edges = 0
        for u, v, key, data in gps_graph.edges(keys=True, data=True):
            # Map to merged node IDs
            u_merged = gps_to_osm.get(u, u)
            v_merged = gps_to_osm.get(v, v)
            
            # Check if this edge already exists in merged graph
            if not merged.has_edge(u_merged, v_merged):
                edge: Edge = data['data']
                # Update source/target to merged IDs
                edge.source = u_merged
                edge.target = v_merged
                merged.add_edge(u_merged, v_merged, key=key, data=edge)
                added_edges += 1
            else:
                # Edge exists, update its GPS trace count
                for k in merged[u_merged][v_merged]:
                    existing_edge: Edge = merged[u_merged][v_merged][k]['data']
                    gps_edge: Edge = data['data']
                    existing_edge.gps_trace_count += gps_edge.gps_trace_count
        
        logger.info(f"Merged graphs: added {added_edges} new edges from GPS traces")
        logger.info(f"Final graph: {merged.number_of_nodes()} nodes, {merged.number_of_edges()} edges")
        
        return merged

