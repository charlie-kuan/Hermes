"""GPS trace data processor for popularity analysis."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import json
import uuid

import networkx as nx
from loguru import logger
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points
import numpy as np

from app.models.domain import Edge, Node, NodeType, TrailDifficulty
from app.utils.geo_utils import haversine_distance


class GPSTraceProcessor:
    """Processes GPS traces to determine trail popularity."""

    def __init__(self):
        self.trace_cache = {}  # Cache loaded traces by area
        self._last_trace_counts = {}  # Store last calculated trace counts
        
    def calculate_trace_based_popularity(
        self,
        graph: nx.MultiDiGraph,
        gps_traces: List[List[Tuple[float, float]]],
        buffer_distance: float = 30.0
    ) -> Dict[Tuple[str, str], float]:
        """
        Calculate edge popularity based on GPS traces.
        
        Args:
            graph: Trail network graph
            gps_traces: List of GPS traces, each trace is a list of (lat, lon) points
            buffer_distance: Distance in meters to match traces to edges
            
        Returns:
            Dictionary mapping (source_id, target_id) to popularity score
        """
        logger.info(f"Calculating popularity from {len(gps_traces)} GPS traces")
        
        # Count traces passing near each edge
        edge_trace_counts = defaultdict(int)
        
        for trace_idx, trace in enumerate(gps_traces):
            if len(trace) < 2:
                continue
                
            # Convert trace to LineString for efficient spatial operations
            trace_line = LineString([(lon, lat) for lat, lon in trace])
            
            # Check which edges this trace passes near
            for u, v, key, data in graph.edges(keys=True, data=True):
                edge: Edge = data['data']
                
                # Get edge geometry or construct from nodes
                if edge.geometry:
                    edge_line = LineString([(lon, lat) for lat, lon in edge.geometry])
                else:
                    node_u: Node = graph.nodes[u]['data']
                    node_v: Node = graph.nodes[v]['data']
                    edge_line = LineString([
                        (node_u.lon, node_u.lat),
                        (node_v.lon, node_v.lat)
                    ])
                
                # Check if trace passes near this edge
                if self._trace_matches_edge(trace_line, edge_line, buffer_distance):
                    edge_trace_counts[(u, v, key)] += 1
            
            if (trace_idx + 1) % 100 == 0:
                logger.debug(f"Processed {trace_idx + 1}/{len(gps_traces)} traces")
        
        # Save counts for access in enrich_graph
        self._last_trace_counts = edge_trace_counts
        
        # Convert counts to normalized popularity scores (0.5 - 2.5)
        popularity_scores = self._normalize_trace_counts(edge_trace_counts, len(gps_traces))
        
        logger.info(f"Calculated popularity for {len(popularity_scores)} edges")
        return popularity_scores
    
    def _trace_matches_edge(
        self,
        trace_line: LineString,
        edge_line: LineString,
        buffer_distance: float
    ) -> bool:
        """
        Check if a GPS trace passes near an edge.
        
        Uses Hausdorff distance approximation for efficiency.
        """
        # Quick distance check
        distance = trace_line.distance(edge_line)
        
        # Convert to meters (approximate, assumes degrees at mid-latitudes)
        distance_meters = distance * 111000  # 1 degree ≈ 111km
        
        return distance_meters <= buffer_distance
    
    def _normalize_trace_counts(
        self,
        trace_counts: Dict[Tuple[str, str, int], int],
        total_traces: int
    ) -> Dict[Tuple[str, str], float]:
        """
        Normalize trace counts to popularity scores.
        
        Maps counts to scores:
        - 0 traces: 0.5 (unpopular)
        - Median: 1.0 (average)
        - Top 10%: 2.0-2.5 (very popular)
        """
        if not trace_counts:
            return {}
        
        # Get count statistics
        counts = list(trace_counts.values())
        counts.sort()
        
        if len(counts) == 0:
            return {}
        
        median_count = counts[len(counts) // 2]
        p90_count = counts[int(len(counts) * 0.9)] if len(counts) > 10 else counts[-1]
        
        # Normalize scores
        popularity_scores = {}
        
        for (u, v, key), count in trace_counts.items():
            if count == 0:
                score = 0.5
            elif count <= median_count:
                # 0.5 to 1.0 for below median
                score = 0.5 + 0.5 * (count / median_count)
            elif count <= p90_count:
                # 1.0 to 2.0 for median to p90
                score = 1.0 + 1.0 * ((count - median_count) / (p90_count - median_count))
            else:
                # 2.0 to 2.5 for top 10%
                score = 2.0 + 0.5 * min(1.0, (count - p90_count) / (p90_count * 0.5))
            
            popularity_scores[(u, v)] = score
        
        return popularity_scores
    
    def load_gps_traces_from_osm(
        self,
        bbox: List[float],
        cache_dir: Path = Path("./data/gps_traces")
    ) -> List[List[Tuple[float, float]]]:
        """
        Load GPS traces from OpenStreetMap GPS trace data.
        
        Note: This requires downloading GPS trace data from OSM.
        You can use OSM API: https://api.openstreetmap.org/api/0.6/trackpoints?bbox=...
        
        Args:
            bbox: [min_lat, min_lon, max_lat, max_lon]
            cache_dir: Directory to cache downloaded traces
            
        Returns:
            List of GPS traces
        """
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        min_lat, min_lon, max_lat, max_lon = bbox
        cache_file = cache_dir / f"traces_{min_lat}_{min_lon}_{max_lat}_{max_lon}.json"
        
        # Check cache
        if cache_file.exists():
            logger.info(f"Loading GPS traces from cache: {cache_file}")
            with open(cache_file, 'r') as f:
                traces_data = json.load(f)
                return [[(p['lat'], p['lon']) for p in trace] for trace in traces_data]
        
        # TODO: Implement OSM GPS trace download
        # For now, return empty list
        logger.warning("GPS trace download not implemented yet. Use load_gps_traces_from_file()")
        return []
    
    def load_gps_traces_from_gpx_files(
        self,
        gpx_directory: Path
    ) -> List[List[Tuple[float, float]]]:
        """
        Load GPS traces from GPX files in a directory.
        
        Args:
            gpx_directory: Directory containing .gpx files
            
        Returns:
            List of GPS traces
        """
        import gpxpy
        
        traces = []
        gpx_files = list(gpx_directory.glob("*.gpx"))
        
        logger.info(f"Loading {len(gpx_files)} GPX files from {gpx_directory}")
        
        for gpx_file in gpx_files:
            try:
                with open(gpx_file, 'r') as f:
                    gpx = gpxpy.parse(f)
                    
                    for track in gpx.tracks:
                        for segment in track.segments:
                            if len(segment.points) >= 2:
                                trace = [(point.latitude, point.longitude) 
                                        for point in segment.points]
                                traces.append(trace)
            
            except Exception as e:
                logger.warning(f"Failed to parse {gpx_file}: {e}")
        
        logger.info(f"Loaded {len(traces)} GPS traces from GPX files")
        return traces
    
    def load_gps_traces_from_geojson(
        self,
        geojson_file: Path
    ) -> List[List[Tuple[float, float]]]:
        """
        Load GPS traces from GeoJSON file.
        
        Expected format: FeatureCollection with LineString features.
        
        Args:
            geojson_file: Path to GeoJSON file
            
        Returns:
            List of GPS traces
        """
        logger.info(f"Loading GPS traces from {geojson_file}")
        
        with open(geojson_file, 'r') as f:
            data = json.load(f)
        
        traces = []
        
        if data.get('type') == 'FeatureCollection':
            for feature in data.get('features', []):
                geometry = feature.get('geometry', {})
                
                if geometry.get('type') == 'LineString':
                    coords = geometry.get('coordinates', [])
                    # GeoJSON uses [lon, lat], convert to [lat, lon]
                    trace = [(lat, lon) for lon, lat in coords]
                    if len(trace) >= 2:
                        traces.append(trace)
                
                elif geometry.get('type') == 'MultiLineString':
                    for line in geometry.get('coordinates', []):
                        trace = [(lat, lon) for lon, lat in line]
                        if len(trace) >= 2:
                            traces.append(trace)
        
        logger.info(f"Loaded {len(traces)} GPS traces from GeoJSON")
        return traces
    
    def calculate_traces_bbox(
        self,
        gps_traces: List[List[Tuple[float, float]]]
    ) -> Optional[List[float]]:
        """
        Calculate the bounding box that covers all GPS traces.
        
        Args:
            gps_traces: List of GPS traces, each trace is a list of (lat, lon) points
            
        Returns:
            Bounding box [min_lat, min_lon, max_lat, max_lon] or None if no traces
        """
        if not gps_traces:
            return None
        
        all_lats = []
        all_lons = []
        
        for trace in gps_traces:
            for lat, lon in trace:
                all_lats.append(lat)
                all_lons.append(lon)
        
        if not all_lats:
            return None
        
        min_lat = min(all_lats)
        max_lat = max(all_lats)
        min_lon = min(all_lons)
        max_lon = max(all_lons)
        
        # Add small buffer (~500m) to ensure edge nodes are included
        buffer = 0.005  # ~500 meters
        
        return [
            min_lat - buffer,
            min_lon - buffer,
            max_lat + buffer,
            max_lon + buffer
        ]
    
    def enrich_graph_with_trace_popularity(
        self,
        graph: nx.MultiDiGraph,
        gps_traces: List[List[Tuple[float, float]]],
        blend_factor: float = 0.7
    ) -> None:
        """
        Update graph edges with GPS trace-based popularity scores.
        
        Args:
            graph: Trail network graph to update
            gps_traces: List of GPS traces
            blend_factor: How much to weight trace data vs OSM attributes (0-1)
                         0 = only OSM, 1 = only GPS traces, 0.5 = equal weight
        """
        # Calculate trace-baself._last_trace_counts
        trace_popularity = self.calculate_trace_based_popularity(graph, gps_traces)
        
        # Store raw trace counts for later access
        edge_trace_counts = defaultdict(int)
        
        # Update edges
        updated_count = 0
        for u, v, key, data in graph.edges(keys=True, data=True):
            edge: Edge = data['data']
            
            # Get trace popularity for this edge
            trace_score = trace_popularity.get((u, v), 0.5)
            trace_count = edge_trace_counts.get((u, v, key), 0)
            
            # Blend with existing OSM-based popularity
            original_score = edge.osm_popularity  # Use original OSM score
            blended_score = (1 - blend_factor) * original_score + blend_factor * trace_score
            
            # Update edge
            edge.popularity_score = blended_score
            edge.gps_trace_count = trace_count
            updated_count += 1
        
        logger.info(f"Updated popularity scores for {updated_count} edges "
                   f"(blend factor: {blend_factor})")

    def build_graph_from_gps_traces(
        self,
        gps_traces: List[List[Tuple[float, float]]],
        simplify_tolerance: float = 0.0001,  # ~11 meters
        intersection_threshold: float = 50.0  # meters
    ) -> nx.MultiDiGraph:
        """
        Build a trail network graph directly from GPS traces.
        
        This is useful when OSM data is insufficient. The function will:
        1. Calculate actual coverage bbox from GPS traces
        2. Simplify traces to reduce noise
        3. Find intersection points between traces
        4. Create nodes at intersections and endpoints
        5. Create edges between nodes based on trace segments
        
        Args:
            gps_traces: List of GPS traces, each trace is a list of (lat, lon) points
            simplify_tolerance: Tolerance for Douglas-Peucker simplification (degrees)
            intersection_threshold: Distance threshold to consider points as intersections (meters)
            
        Returns:
            NetworkX MultiDiGraph with trail network
        """
        logger.info(f"Building graph from {len(gps_traces)} GPS traces")
        
        if not gps_traces:
            logger.warning("No GPS traces provided")
            return nx.MultiDiGraph()
        
        # Calculate actual bbox from GPS traces
        actual_bbox = self.calculate_traces_bbox(gps_traces)
        if actual_bbox:
            min_lat, min_lon, max_lat, max_lon = actual_bbox
            logger.info(
                f"GPS traces coverage: lat [{min_lat:.5f}, {max_lat:.5f}], "
                f"lon [{min_lon:.5f}, {max_lon:.5f}]"
            )
        
        G = nx.MultiDiGraph()
        
        # Step 1: Simplify traces and convert to LineStrings
        simplified_traces = []
        for trace in gps_traces:
            if len(trace) < 2:
                continue
            
            # Convert to LineString (lon, lat for shapely)
            line = LineString([(lon, lat) for lat, lon in trace])
            
            # Simplify to reduce GPS noise
            if simplify_tolerance > 0:
                line = line.simplify(simplify_tolerance, preserve_topology=True)
            
            simplified_traces.append(line)
        
        logger.info(f"Simplified {len(simplified_traces)} traces")
        
        # Step 2: Find intersection points and endpoints
        node_locations = []  # List of (lat, lon) for potential nodes
        
        # Add all endpoints
        for line in simplified_traces:
            coords = list(line.coords)
            # Start point
            lon, lat = coords[0]
            node_locations.append((lat, lon))
            # End point
            lon, lat = coords[-1]
            node_locations.append((lat, lon))
        
        # Find intersections between traces
        for i, line1 in enumerate(simplified_traces):
            for j, line2 in enumerate(simplified_traces[i+1:], start=i+1):
                if line1.intersects(line2):
                    intersection = line1.intersection(line2)
                    if intersection.geom_type == 'Point':
                        lon, lat = intersection.x, intersection.y
                        node_locations.append((lat, lon))
                    elif intersection.geom_type == 'MultiPoint':
                        for point in intersection.geoms:
                            lon, lat = point.x, point.y
                            node_locations.append((lat, lon))
        
        logger.info(f"Found {len(node_locations)} potential node locations")
        
        # Step 3: Cluster nearby points to create unique nodes
        nodes = self._cluster_nodes(node_locations, intersection_threshold)
        logger.info(f"Clustered into {len(nodes)} unique nodes")
        
        # Step 4: Add nodes to graph
        node_id_map = {}  # Map (lat, lon) -> node_id
        for idx, (lat, lon) in enumerate(nodes):
            node_id = f"gps_node_{idx}"
            node = Node(
                id=node_id,
                node_type=NodeType.INTERSECTION,
                lat=lat,
                lon=lon,
                elevation=0.0,  # Will be enriched later
                name=None,
                amenities=[]
            )
            G.add_node(node_id, data=node)
            node_id_map[(lat, lon)] = node_id
        
        # Step 5: Create edges from traces
        edge_counts = defaultdict(int)  # Count how many traces use each edge
        
        for trace_line in simplified_traces:
            # Find which nodes this trace passes through
            trace_nodes = self._match_trace_to_nodes(trace_line, nodes, intersection_threshold)
            
            if len(trace_nodes) < 2:
                continue
            
            # Create edges between consecutive nodes
            for i in range(len(trace_nodes) - 1):
                node1 = trace_nodes[i]
                node2 = trace_nodes[i + 1]
                
                node1_id = node_id_map[node1]
                node2_id = node_id_map[node2]
                
                edge_key = (node1_id, node2_id)
                edge_counts[edge_key] += 1
        
        # Step 6: Add edges to graph with popularity based on trace count
        for (source_id, target_id), count in edge_counts.items():
            if source_id == target_id:
                continue
                
            source_node: Node = G.nodes[source_id]['data']
            target_node: Node = G.nodes[target_id]['data']
            
            # Calculate edge properties
            distance = haversine_distance(
                source_node.lat, source_node.lon,
                target_node.lat, target_node.lon
            )
            
            # Popularity based on trace count
            # More traces = higher popularity
            if count == 1:
                popularity = 0.5
            elif count <= 3:
                popularity = 1.0
            elif count <= 10:
                popularity = 1.5
            else:
                popularity = 2.0 + min(0.5, (count - 10) * 0.05)
            
            edge = Edge(
                source=source_id,
                target=target_id,
                distance=distance,
                elevation_gain=0.0,  # Will be calculated later
                elevation_loss=0.0,
                difficulty=TrailDifficulty.MODERATE,  # Default, can be refined
                surface='unpaved',
                trail_name=None,
                geometry=[(source_node.lat, source_node.lon), 
                         (target_node.lat, target_node.lon)],
                popularity_score=popularity,
                gps_trace_count=count,
                osm_popularity=0.5,  # No OSM data
                trail_visibility=None,
                route_ref=None,
                osm_tags={}
            )
            
            # Use count as key to allow multiple edges between same nodes
            G.add_edge(source_id, target_id, key=0, data=edge)
        
        logger.info(f"Built graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        return G
    
    def _cluster_nodes(
        self,
        locations: List[Tuple[float, float]],
        threshold: float
    ) -> List[Tuple[float, float]]:
        """
        Cluster nearby node locations into single nodes.
        
        Args:
            locations: List of (lat, lon) tuples
            threshold: Distance threshold in meters
            
        Returns:
            List of clustered (lat, lon) locations
        """
        if not locations:
            return []
        
        # Simple greedy clustering
        clusters = []
        used = set()
        
        for i, loc1 in enumerate(locations):
            if i in used:
                continue
                
            # Start new cluster
            cluster_lats = [loc1[0]]
            cluster_lons = [loc1[1]]
            used.add(i)
            
            # Find nearby points
            for j, loc2 in enumerate(locations):
                if j in used:
                    continue
                    
                dist = haversine_distance(loc1[0], loc1[1], loc2[0], loc2[1])
                if dist <= threshold:
                    cluster_lats.append(loc2[0])
                    cluster_lons.append(loc2[1])
                    used.add(j)
            
            # Use centroid of cluster
            avg_lat = sum(cluster_lats) / len(cluster_lats)
            avg_lon = sum(cluster_lons) / len(cluster_lons)
            clusters.append((avg_lat, avg_lon))
        
        return clusters
    
    def _match_trace_to_nodes(
        self,
        trace_line: LineString,
        nodes: List[Tuple[float, float]],
        threshold: float
    ) -> List[Tuple[float, float]]:
        """
        Find which nodes a trace passes through.
        
        Args:
            trace_line: Shapely LineString of the trace
            nodes: List of node (lat, lon) locations
            threshold: Distance threshold in meters
            
        Returns:
            Ordered list of nodes that the trace passes through
        """
        matched_nodes = []
        
        for node_lat, node_lon in nodes:
            # Create point for node (lon, lat for shapely)
            node_point = Point(node_lon, node_lat)
            
            # Check distance to trace
            distance = trace_line.distance(node_point)
            distance_meters = distance * 111000  # Approximate conversion
            
            if distance_meters <= threshold:
                # Find position along trace
                position = trace_line.project(node_point)
                matched_nodes.append((position, (node_lat, node_lon)))
        
        # Sort by position along trace
        matched_nodes.sort(key=lambda x: x[0])
        
        # Return just the node locations
        return [node for _, node in matched_nodes]

    def split_edge_at_point(
        self,
        graph: nx.MultiDiGraph,
        edge_key: Tuple[str, str, int],
        split_lat: float,
        split_lon: float
    ) -> Optional[str]:
        """
        Split an edge at a given point, creating a new intermediate node.
        
        This allows users to start/end routes at arbitrary points along trails,
        not just at existing nodes.
        
        Args:
            graph: Trail network graph
            edge_key: (source_id, target_id, key) tuple identifying the edge
            split_lat: Latitude of split point
            split_lon: Longitude of split point
            
        Returns:
            ID of the new intermediate node, or None if split failed
        """
        source_id, target_id, key = edge_key
        
        # Get the edge
        if not graph.has_edge(source_id, target_id, key=key):
            logger.warning(f"Edge {source_id} -> {target_id} (key={key}) not found")
            return None
        
        edge_data = graph.edges[source_id, target_id, key]
        edge: Edge = edge_data['data']
        
        # Get source and target nodes
        source_node: Node = graph.nodes[source_id]['data']
        target_node: Node = graph.nodes[target_id]['data']
        
        # Verify split point is reasonably close to edge
        edge_line = LineString([
            (source_node.lon, source_node.lat),
            (target_node.lon, target_node.lat)
        ])
        split_point = Point(split_lon, split_lat)
        distance = edge_line.distance(split_point) * 111000  # meters
        
        if distance > 100:  # More than 100m away
            logger.warning(f"Split point is {distance:.1f}m from edge, too far")
            return None
        
        # Create new intermediate node
        new_node_id = f"split_{uuid.uuid4().hex[:8]}"
        new_node = Node(
            id=new_node_id,
            node_type=NodeType.INTERSECTION,
            lat=split_lat,
            lon=split_lon,
            elevation=self._interpolate_elevation(
                source_node, target_node, split_lat, split_lon
            ),
            name=None,
            amenities=[]
        )
        
        # Add new node to graph
        graph.add_node(new_node_id, data=new_node)
        
        # Calculate distances
        dist_source_to_split = haversine_distance(
            source_node.lat, source_node.lon, split_lat, split_lon
        )
        dist_split_to_target = haversine_distance(
            split_lat, split_lon, target_node.lat, target_node.lon
        )
        
        # Calculate proportion for interpolating edge properties
        total_dist = edge.distance
        if total_dist > 0:
            ratio = dist_source_to_split / total_dist
        else:
            ratio = 0.5
        
        # Create first edge segment (source -> split)
        edge1 = Edge(
            source=source_id,
            target=new_node_id,
            distance=dist_source_to_split,
            elevation_gain=edge.elevation_gain * ratio,
            elevation_loss=edge.elevation_loss * ratio,
            difficulty=edge.difficulty,
            surface=edge.surface,
            trail_name=edge.trail_name,
            geometry=[
                (source_node.lat, source_node.lon),
                (split_lat, split_lon)
            ],
            popularity_score=edge.popularity_score,
            gps_trace_count=edge.gps_trace_count,
            osm_popularity=edge.osm_popularity,
            trail_visibility=edge.trail_visibility,
            route_ref=edge.route_ref,
            osm_tags=edge.osm_tags
        )
        
        # Create second edge segment (split -> target)
        edge2 = Edge(
            source=new_node_id,
            target=target_id,
            distance=dist_split_to_target,
            elevation_gain=edge.elevation_gain * (1 - ratio),
            elevation_loss=edge.elevation_loss * (1 - ratio),
            difficulty=edge.difficulty,
            surface=edge.surface,
            trail_name=edge.trail_name,
            geometry=[
                (split_lat, split_lon),
                (target_node.lat, target_node.lon)
            ],
            popularity_score=edge.popularity_score,
            gps_trace_count=edge.gps_trace_count,
            osm_popularity=edge.osm_popularity,
            trail_visibility=edge.trail_visibility,
            route_ref=edge.route_ref,
            osm_tags=edge.osm_tags
        )
        
        # Remove original edge
        graph.remove_edge(source_id, target_id, key=key)
        
        # Add new edge segments
        graph.add_edge(source_id, new_node_id, key=0, data=edge1)
        graph.add_edge(new_node_id, target_id, key=0, data=edge2)
        
        logger.info(f"Split edge {source_id} -> {target_id} at ({split_lat:.5f}, {split_lon:.5f}), "
                   f"created new node {new_node_id}")
        
        return new_node_id
    
    def _interpolate_elevation(
        self,
        node1: Node,
        node2: Node,
        lat: float,
        lon: float
    ) -> float:
        """
        Interpolate elevation at a point between two nodes.
        
        Args:
            node1: First node
            node2: Second node
            lat: Latitude of point
            lon: Longitude of point
            
        Returns:
            Interpolated elevation
        """
        dist1 = haversine_distance(node1.lat, node1.lon, lat, lon)
        dist2 = haversine_distance(lat, lon, node2.lat, node2.lon)
        
        total_dist = dist1 + dist2
        if total_dist == 0:
            return node1.elevation
        
        # Linear interpolation
        ratio = dist1 / total_dist
        return node1.elevation + (node2.elevation - node1.elevation) * ratio

    def find_nearest_edge(
        self,
        graph: nx.MultiDiGraph,
        lat: float,
        lon: float,
        max_distance: float = 100.0
    ) -> Optional[Tuple[str, str, int, float]]:
        """
        Find the nearest edge to a given point.
        
        This is useful for finding where to split an edge when a user
        specifies a start/end point that's not at an existing node.
        
        Args:
            graph: Trail network graph
            lat: Latitude
            lon: Longitude
            max_distance: Maximum distance in meters
            
        Returns:
            Tuple of (source_id, target_id, key, distance) or None
        """
        point = Point(lon, lat)
        min_distance = float('inf')
        nearest_edge = None
        
        for u, v, key, data in graph.edges(keys=True, data=True):
            edge: Edge = data['data']
            
            # Get edge geometry
            if edge.geometry and len(edge.geometry) >= 2:
                edge_line = LineString([(lon, lat) for lat, lon in edge.geometry])
            else:
                node_u: Node = graph.nodes[u]['data']
                node_v: Node = graph.nodes[v]['data']
                edge_line = LineString([
                    (node_u.lon, node_u.lat),
                    (node_v.lon, node_v.lat)
                ])
            
            # Calculate distance
            distance = edge_line.distance(point) * 111000  # meters
            
            if distance < min_distance:
                min_distance = distance
                nearest_edge = (u, v, key, distance)
        
        if nearest_edge and min_distance <= max_distance:
            return nearest_edge
        
        return None


class GPSTraceSource:
    """Helper class for different GPS trace data sources."""
    
    @staticmethod
    def from_strava_heatmap(bbox: List[float]) -> List[List[Tuple[float, float]]]:
        """
        Load traces from Strava Global Heatmap.
        
        Note: Requires Strava API access or scraping heatmap tiles.
        This is a placeholder for future implementation.
        """
        raise NotImplementedError("Strava heatmap integration not yet implemented")
    
    @staticmethod
    def from_osm_api(bbox: List[float], api_url: str = "https://api.openstreetmap.org") -> List[List[Tuple[float, float]]]:
        """
        Download GPS traces from OSM API.
        
        API endpoint: GET /api/0.6/trackpoints?bbox=min_lon,min_lat,max_lon,max_lat&page=0
        """
        raise NotImplementedError("OSM API GPS trace download not yet implemented")
    
    @staticmethod  
    def from_wikiloc(area: str) -> List[List[Tuple[float, float]]]:
        """
        Load traces from Wikiloc.
        
        Note: Requires API access or web scraping.
        """
        raise NotImplementedError("Wikiloc integration not yet implemented")
