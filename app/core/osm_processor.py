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

            # Download POIs (peaks, huts, etc.)
            pois = self._download_pois(bbox)
            logger.info(f"Downloaded {len(pois)} POIs")

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
        """Download points of interest from OSM."""
        min_lat, min_lon, max_lat, max_lon = bbox
        pois = []

        # POI tags to download
        poi_tags = {
            'natural': ['peak', 'saddle'],
            'tourism': ['alpine_hut', 'wilderness_hut', 'camp_site', 'viewpoint'],
            'amenity': ['shelter', 'drinking_water'],
            'highway': ['trailhead']
        }

        for key, values in poi_tags.items():
            for value in values:
                try:
                    features = ox.features_from_bbox(
                        north=max_lat,
                        south=min_lat,
                        east=max_lon,
                        west=min_lon,
                        tags={key: value}
                    )

                    for idx, feature in features.iterrows():
                        # Handle both Point and other geometries
                        if hasattr(feature.geometry, 'centroid'):
                            centroid = feature.geometry.centroid
                            lat, lon = centroid.y, centroid.x
                        else:
                            continue

                        poi = {
                            'lat': lat,
                            'lon': lon,
                            'type': value,
                            'name': feature.get('name', None),
                            'elevation': feature.get('ele', None)
                        }
                        pois.append(poi)

                except Exception as e:
                    logger.debug(f"No {key}={value} found: {e}")

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
            
            edge_data = Edge(
                source=str(u),
                target=str(v),
                distance=data.get('length', 0.0),
                elevation_gain=0.0,  # Will be calculated later
                elevation_loss=0.0,
                difficulty=self._map_difficulty(data),
                surface=data.get('surface', 'unpaved'),
                trail_name=data.get('name', None),
                geometry=[],
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
        """Enrich nodes with elevation data from SRTM."""
        logger.info("Enriching elevation data...")
        
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
        import time
        
        def fetch_elevation_safe(node):
            """Safely fetch elevation with error handling."""
            try:
                elevation = self.elevation_processor.get_elevation(node.lat, node.lon)
                return elevation
            except Exception as e:
                logger.debug(f"Failed to get elevation: {e}")
                return None
        
        nodes_processed = 0
        nodes_with_elevation = 0
        max_nodes_to_process = 50  # Limit to avoid long delays
        timeout_per_node = 3  # 3 seconds per node
        
        # Use thread pool for parallel processing with timeout
        with ThreadPoolExecutor(max_workers=3) as executor:
            for node_id, data in G.nodes(data=True):
                node: Node = data['data']

                # Skip if already has elevation
                if node.elevation and node.elevation > 0:
                    nodes_with_elevation += 1
                    continue

                # Skip after processing limit
                if nodes_processed >= max_nodes_to_process:
                    # Use default elevation for remaining nodes
                    if node.elevation <= 0:
                        node.elevation = 2500.0
                    continue

                # Fetch from SRTM with timeout
                try:
                    future = executor.submit(fetch_elevation_safe, node)
                    elevation = future.result(timeout=timeout_per_node)
                    
                    if elevation is not None and elevation > 0:
                        node.elevation = elevation
                        nodes_with_elevation += 1
                    else:
                        # Use default for invalid data
                        node.elevation = 2500.0
                        
                except FutureTimeoutError:
                    logger.warning(f"Elevation fetch timeout for node {node_id}")
                    node.elevation = 2500.0
                except Exception as e:
                    logger.debug(f"Error fetching elevation for node {node_id}: {e}")
                    node.elevation = 2500.0
                
                nodes_processed += 1
        
        # Set default elevation for any remaining nodes without elevation
        for node_id, data in G.nodes(data=True):
            node: Node = data['data']
            if node.elevation <= 0:
                node.elevation = 2500.0
        
        logger.info(f"Enriched elevation data: {nodes_with_elevation}/{G.number_of_nodes()} nodes (processed {nodes_processed}, rest use default)")

    def _calculate_edge_metrics(self, G: nx.MultiDiGraph) -> None:
        """Calculate elevation gain/loss for edges."""
        for u, v, key, data in G.edges(keys=True, data=True):
            edge: Edge = data['data']

            # Get node elevations
            source_node: Node = G.nodes[u]['data']
            target_node: Node = G.nodes[v]['data']

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
