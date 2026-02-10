"""OSM data processing and graph construction."""

from typing import Dict, List, Optional, Set, Tuple

import networkx as nx
import osmnx as ox
from loguru import logger

from app.config import settings
from app.core.elevation_processor import ElevationProcessor
from app.models.domain import Edge, Node, NodeType, TrailDifficulty
from app.utils.geo_utils import haversine_distance


class OSMProcessor:
    """Processes OpenStreetMap data into trail network graphs."""

    def __init__(self):
        self.elevation_processor = ElevationProcessor()
        ox.settings.user_agent = settings.osm_user_agent
        ox.settings.use_cache = True
        ox.settings.timeout = 30  # 30 seconds timeout for OSM queries
        ox.settings.cache_folder = str(settings.osm_cache_dir)

    def download_trail_network(
        self,
        bbox: List[float],
        area_name: Optional[str] = None
    ) -> nx.MultiDiGraph:
        """
        Download and process trail network from OSM.

        Args:
            bbox: [min_lat, min_lon, max_lat, max_lon]
            area_name: Optional area name for logging

        Returns:
            NetworkX MultiDiGraph with trail network
        """
        logger.info(f"Downloading OSM data for {area_name or 'area'}: {bbox}")

        # Create graph
        G = nx.MultiDiGraph()

        try:
            # Download trail ways
            trails = self._download_trails(bbox)
            logger.info(f"Downloaded {len(trails)} trail ways")

            # Download POIs (peaks, huts, etc.) - optional, disabled by default
            pois = []
            if settings.osm_download_pois:
                pois = self._download_pois(bbox)
                logger.info(f"Downloaded {len(pois)} POIs")
            else:
                logger.debug(f"POI download disabled (osm_download_pois=False)")

            # Build graph from trails
            self._build_graph_from_trails(G, trails)

            # Add POI nodes
            self._add_poi_nodes(G, pois)

            # Enrich with elevation data
            self._enrich_elevations(G)

            # Calculate edge metrics
            self._calculate_edge_metrics(G)

            logger.info(f"Built graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")

            return G

        except Exception as e:
            logger.error(f"Failed to download trail network: {e}")
            raise

    def _download_trails(self, bbox: List[float]) -> dict:
        """Download trail ways from OSM."""
        min_lat, min_lon, max_lat, max_lon = bbox

        # Custom filter for hiking trails - include more trail types
        custom_filter = (
            '["highway"~"path|track|footway|trail|bridleway"]'
            '["access"!~"private"]'
        )

        try:
            # Download as graph first, then convert
            G = ox.graph_from_bbox(
                north=max_lat,
                south=min_lat,
                east=max_lon,
                west=min_lon,
                custom_filter=custom_filter,
                network_type='all',
                simplify=False
            )

            # Convert to GeoDataFrames
            nodes, edges = ox.graph_to_gdfs(G)

            return {'nodes': nodes, 'edges': edges, 'graph': G}

        except Exception as e:
            logger.warning(f"Failed to download trails with custom filter: {e}")
            # Return empty result
            return {'nodes': None, 'edges': None, 'graph': nx.MultiDiGraph()}

    def _download_pois(self, bbox: List[float]) -> List[dict]:
        """Download points of interest from OSM based on configured tags.
        
        Note: Many POI types have low coverage in Taiwan OSM data.
        Configure osm_poi_tags in settings to only query useful tags.
        """
        min_lat, min_lon, max_lat, max_lon = bbox
        pois = []

        # Parse POI tags from config (format: "key=value")
        poi_queries = {}
        for tag_str in settings.osm_poi_tags:
            try:
                key, value = tag_str.split('=', 1)
                if key not in poi_queries:
                    poi_queries[key] = []
                poi_queries[key].append(value)
            except ValueError:
                logger.warning(f"Invalid POI tag format: {tag_str} (expected 'key=value')")

        if not poi_queries:
            logger.debug("No POI tags configured, skipping POI download")
            return pois

        # Download POIs by batching values per key
        for key, values in poi_queries.items():
            try:
                # Use regex to match any of the values in one query
                value_regex = '|'.join(values) if len(values) > 1 else values[0]
                features = ox.features_from_bbox(
                    bbox=(max_lat, min_lat, max_lon, min_lon),
                    tags={key: value_regex}
                )

                for idx, feature in features.iterrows():
                    # Handle both Point and other geometries
                    if hasattr(feature.geometry, 'centroid'):
                        centroid = feature.geometry.centroid
                        lat, lon = centroid.y, centroid.x
                    else:
                        continue

                    # Determine the specific type from the feature tags
                    feature_type = feature.get(key, values[0])
                    
                    poi = {
                        'lat': lat,
                        'lon': lon,
                        'type': feature_type,
                        'name': feature.get('name', None),
                        'elevation': feature.get('ele', None)
                    }
                    pois.append(poi)

                logger.debug(f"Found {len([p for p in pois if p.get('type') in values])} {key} POIs")

            except Exception as e:
                logger.debug(f"No {key} features found: {e}")

        return pois

    def _build_graph_from_trails(self, G: nx.MultiDiGraph, trails: dict) -> None:
        """Build graph structure from downloaded trail data."""
        if trails.get('graph') is None or trails['graph'].number_of_nodes() == 0:
            logger.warning("No trail data to build graph from")
            return

        osm_graph = trails['graph']
        edges_gdf = trails['edges']

        # Add nodes
        for node_id, data in osm_graph.nodes(data=True):
            node = Node(
                id=str(node_id),
                node_type=NodeType.INTERSECTION,
                lat=data['y'],
                lon=data['x'],
                elevation=data.get('elevation', 0.0),
                name=None,
                amenities=[]
            )
            G.add_node(node.id, data=node)

        # Add edges
        for u, v, key, data in osm_graph.edges(keys=True, data=True):
            # Get edge attributes
            osm_popularity = self._calculate_popularity_score(data)

            # Extract geometry from edges_gdf if available
            geometry = []
            try:
                # Find the corresponding edge in the GeoDataFrame
                edge_row = edges_gdf[(edges_gdf['u'] == u) & (edges_gdf['v'] == v) & (edges_gdf['key'] == key)]
                if not edge_row.empty and hasattr(edge_row.iloc[0], 'geometry'):
                    geom = edge_row.iloc[0].geometry
                    if geom is not None and hasattr(geom, 'coords'):
                        # Extract coordinates from LineString
                        # OSM geometry is (lon, lat), we need (lat, lon)
                        geometry = [(lat, lon) for lon, lat in geom.coords]
                        logger.debug(f"Extracted {len(geometry)} points from edge {u}->{v}")
            except Exception as e:
                logger.debug(f"Could not extract geometry for edge {u}->{v}: {e}")

            edge_data = Edge(
                source=str(u),
                target=str(v),
                distance=data.get('length', 0.0),
                elevation_gain=0.0,  # Will be calculated later
                elevation_loss=0.0,
                difficulty=self._map_difficulty(data),
                surface=data.get('surface', 'unpaved'),
                trail_name=data.get('name', None),
                geometry=geometry,
                # Popularity indicators
                popularity_score=osm_popularity,
                gps_trace_count=0,
                osm_popularity=osm_popularity,  # Save original OSM popularity
                trail_visibility=data.get('trail_visibility', None),
                route_ref=data.get('ref', None),
                osm_tags={
                    'sac_scale': data.get('sac_scale'),
                    'highway': data.get('highway'),
                    'surface': data.get('surface'),
                    'tracktype': data.get('tracktype'),
                    'trail_visibility': data.get('trail_visibility'),
                    'mtb:scale': data.get('mtb:scale'),
                }
            )

            G.add_edge(str(u), str(v), key=key, data=edge_data)

    def _add_poi_nodes(self, G: nx.MultiDiGraph, pois: List[dict]) -> None:
        """Add POI nodes to the graph."""
        for poi in pois:
            node_type = self._map_node_type(poi['type'])

            node = Node(
                id=f"poi_{poi['lat']}_{poi['lon']}",
                node_type=node_type,
                lat=poi['lat'],
                lon=poi['lon'],
                elevation=float(poi['elevation']) if poi['elevation'] else 0.0,
                name=poi.get('name'),
                amenities=self._get_amenities(poi['type'])
            )

            # Find nearest trail node to connect POI
            nearest_node = self._find_nearest_node(G, poi['lat'], poi['lon'])

            if nearest_node:
                G.add_node(node.id, data=node)

                # Add connecting edges
                distance = haversine_distance(
                    poi['lat'], poi['lon'],
                    G.nodes[nearest_node]['data'].lat,
                    G.nodes[nearest_node]['data'].lon
                )

                # Only connect if within 500m
                if distance < 500:
                    edge = Edge(
                        source=nearest_node,
                        target=node.id,
                        distance=distance,
                        elevation_gain=0.0,
                        elevation_loss=0.0,
                        difficulty=TrailDifficulty.EASY,
                        surface='unpaved',
                        popularity_score=1.0,
                        gps_trace_count=0,
                        osm_popularity=1.0
                    )
                    G.add_edge(nearest_node, node.id, key=0, data=edge)
                    
                    # Reverse edge for bidirectional
                    edge_reverse = Edge(
                        source=node.id,
                        target=nearest_node,
                        distance=distance,
                        elevation_gain=0.0,
                        elevation_loss=0.0,
                        difficulty=TrailDifficulty.EASY,
                        surface='unpaved',
                        popularity_score=1.0,
                        gps_trace_count=0,
                        osm_popularity=1.0
                    )
                    G.add_edge(node.id, nearest_node, key=0, data=edge_reverse)

    def _enrich_elevations(self, G: nx.MultiDiGraph) -> None:
        """Enrich nodes with elevation data from local DEM or SRTM."""
        logger.info(f"Enriching elevation data for {G.number_of_nodes()} nodes using local DEM...")

        nodes_processed = 0
        nodes_with_elevation = 0
        nodes_failed = 0

        # Process all nodes (local DEM is fast, no need for limits)
        for node_id, data in G.nodes(data=True):
            node: Node = data['data']

            # Skip if already has valid elevation
            if node.elevation and node.elevation > 0:
                nodes_with_elevation += 1
                continue

            # Get elevation from local DEM or SRTM
            try:
                elevation = self.elevation_processor.get_elevation(node.lat, node.lon)

                if elevation is not None and elevation > 0:
                    node.elevation = elevation
                    nodes_with_elevation += 1
                else:
                    # Use reasonable default based on Taiwan mountain ranges
                    node.elevation = 2000.0
                    nodes_failed += 1
                    logger.debug(f"No elevation data for node {node_id} at ({node.lat:.4f}, {node.lon:.4f}), using default")

            except Exception as e:
                logger.debug(f"Error fetching elevation for node {node_id}: {e}")
                node.elevation = 2000.0
                nodes_failed += 1

            nodes_processed += 1

            # Progress logging for large graphs
            if nodes_processed % 100 == 0:
                logger.info(f"Processed {nodes_processed}/{G.number_of_nodes()} nodes")

        logger.info(f"Enriched elevation data: {nodes_with_elevation}/{G.number_of_nodes()} nodes successfully, {nodes_failed} nodes using default")

    def _calculate_edge_metrics(self, G: nx.MultiDiGraph) -> None:
        """Calculate elevation gain/loss for edges using detailed geometry."""
        logger.info("Calculating edge metrics with DEM elevation data...")

        edges_processed = 0
        edges_with_geometry = 0

        for u, v, key, data in G.edges(keys=True, data=True):
            edge: Edge = data['data']

            # Get node elevations
            source_node: Node = G.nodes[u]['data']
            target_node: Node = G.nodes[v]['data']

            # If edge has detailed geometry, use it for more accurate elevation profile
            if edge.geometry and len(edge.geometry) > 2:
                try:
                    # Get elevations for all points in the geometry
                    elevations = []
                    geometry_with_elevation = []

                    for lat, lon in edge.geometry:
                        elev = self.elevation_processor.get_elevation(lat, lon)
                        if elev is not None:
                            elevations.append(elev)
                        else:
                            # Fallback to interpolation if elevation not available
                            elevations.append(None)

                    # Interpolate missing elevations
                    if elevations and any(e is not None for e in elevations):
                        elevations = self.elevation_processor.interpolate_missing_elevations(elevations)

                        # Update geometry to include elevation data (lat, lon, elevation)
                        for (lat, lon), elev in zip(edge.geometry, elevations):
                            geometry_with_elevation.append((lat, lon, elev))

                        edge.geometry = geometry_with_elevation

                        # Calculate gain/loss from elevation profile
                        gain, loss = self.elevation_processor.calculate_elevation_gain_loss(elevations)
                        edge.elevation_gain = gain
                        edge.elevation_loss = loss

                        # Update node elevations with geometry endpoints if more accurate
                        if elevations[0] > 0:
                            source_node.elevation = elevations[0]
                        if elevations[-1] > 0:
                            target_node.elevation = elevations[-1]

                        edges_with_geometry += 1
                        logger.debug(f"Edge {u}->{v}: {len(elevations)} elevation points, gain={gain:.1f}m, loss={loss:.1f}m")
                    else:
                        # Fallback to simple calculation
                        self._calculate_simple_elevation_diff(edge, source_node, target_node)

                except Exception as e:
                    logger.debug(f"Error processing geometry for edge {u}->{v}: {e}")
                    # Fallback to simple calculation
                    self._calculate_simple_elevation_diff(edge, source_node, target_node)
            else:
                # No detailed geometry, use simple start/end calculation
                self._calculate_simple_elevation_diff(edge, source_node, target_node)

            edges_processed += 1
            if edges_processed % 100 == 0:
                logger.debug(f"Processed {edges_processed}/{G.number_of_edges()} edges")

        logger.info(f"Calculated metrics for {edges_processed} edges ({edges_with_geometry} with detailed elevation profiles)")

    def _calculate_simple_elevation_diff(self, edge: Edge, source_node: Node, target_node: Node) -> None:
        """Calculate simple elevation gain/loss from start and end points."""
        elev_diff = target_node.elevation - source_node.elevation

        if elev_diff > 0:
            edge.elevation_gain = elev_diff
            edge.elevation_loss = 0.0
        else:
            edge.elevation_gain = 0.0
            edge.elevation_loss = abs(elev_diff)

    def _calculate_popularity_score(self, edge_data: dict) -> float:
        """
        Calculate popularity score based on OSM attributes.
        
        Score factors:
        - Has name: +0.3 (named trails are usually popular)
        - Has ref: +0.4 (official routes)
        - Trail visibility: excellent/good +0.3
        - Better surface: +0.2
        - Highway type: path > track > footway
        
        Returns:
            Score from 0.5 (unpopular) to 2.0 (very popular)
        """
        score = 1.0  # Base score
        
        # Named trails are usually popular
        if edge_data.get('name'):
            score += 0.3
        
        # Official route references (e.g., "GR20", "玉山主峰線")
        if edge_data.get('ref'):
            score += 0.4
        
        # Trail visibility
        visibility = edge_data.get('trail_visibility', '')
        if visibility in ['excellent', 'good']:
            score += 0.3
        elif visibility == 'intermediate':
            score += 0.1
        elif visibility in ['bad', 'horrible', 'no']:
            score -= 0.2
        
        # Surface quality (better surface = more popular/maintained)
        surface = edge_data.get('surface', '')
        if surface in ['paved', 'asphalt', 'concrete']:
            score += 0.2
        elif surface in ['gravel', 'compacted']:
            score += 0.1
        
        # Highway type preference
        highway = edge_data.get('highway', '')
        if highway == 'path':
            score += 0.1  # Paths are typically well-used hiking trails
        
        # SAC scale (easier = more popular with general public)
        sac_scale = edge_data.get('sac_scale', '')
        if sac_scale == 'hiking':
            score += 0.1
        elif sac_scale in ['alpine_hiking', 'demanding_alpine_hiking']:
            score -= 0.1  # Technical routes less popular
        
        # Tracktype (better grade = more maintained = more popular)
        tracktype = edge_data.get('tracktype', '')
        if tracktype in ['grade1', 'grade2']:
            score += 0.1
        
        # Clamp score between 0.5 and 2.0
        return max(0.5, min(2.0, score))

    def _map_difficulty(self, edge_data: dict) -> TrailDifficulty:
        """Map OSM sac_scale to TrailDifficulty."""
        sac_scale = edge_data.get('sac_scale', '')

        mapping = {
            'hiking': TrailDifficulty.EASY,
            'mountain_hiking': TrailDifficulty.MODERATE,
            'demanding_mountain_hiking': TrailDifficulty.DIFFICULT,
            'alpine_hiking': TrailDifficulty.EXPERT,
            'demanding_alpine_hiking': TrailDifficulty.EXPERT,
        }

        return mapping.get(sac_scale, TrailDifficulty.MODERATE)

    def _map_node_type(self, osm_type: str) -> NodeType:
        """Map OSM type to NodeType."""
        mapping = {
            'peak': NodeType.PEAK,
            'alpine_hut': NodeType.HUT,
            'wilderness_hut': NodeType.HUT,
            'camp_site': NodeType.CAMPSITE,
            'viewpoint': NodeType.VIEWPOINT,
            'drinking_water': NodeType.WATER_SOURCE,
            'shelter': NodeType.HUT,
            'trailhead': NodeType.TRAILHEAD,
        }
        return mapping.get(osm_type, NodeType.GENERIC)

    def _get_amenities(self, osm_type: str) -> List[str]:
        """Get amenities list based on OSM type."""
        amenities_map = {
            'alpine_hut': ['shelter', 'accommodation'],
            'wilderness_hut': ['shelter'],
            'camp_site': ['camping'],
            'drinking_water': ['water'],
            'shelter': ['shelter'],
        }
        return amenities_map.get(osm_type, [])

    def _find_nearest_node(self, G: nx.MultiDiGraph, lat: float, lon: float) -> Optional[str]:
        """Find nearest node in graph to given coordinates."""
        if G.number_of_nodes() == 0:
            return None

        min_dist = float('inf')
        nearest = None

        for node_id, data in G.nodes(data=True):
            node: Node = data['data']
            dist = haversine_distance(lat, lon, node.lat, node.lon)

            if dist < min_dist:
                min_dist = dist
                nearest = node_id

        return nearest
