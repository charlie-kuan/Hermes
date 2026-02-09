"""GPS trace data processor for popularity analysis."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import json

import networkx as nx
from loguru import logger
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points

from app.models.domain import Edge, Node
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
