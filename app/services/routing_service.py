"""Routing service for trail network pathfinding."""

import uuid
from typing import List, Optional, Tuple

import networkx as nx
from loguru import logger

from app.core.cost_functions import RoutingCostFunction
from app.exceptions import NoValidPathError
from app.models.domain import Edge, FitnessLevel, Node, Route, RouteSegment, TrailDifficulty
from app.services.graph_service import GraphService


class RoutingService:
    """Handles route planning and pathfinding."""

    def __init__(self, graph_service: GraphService):
        self.graph_service = graph_service
        self.cost_function = RoutingCostFunction()

    def plan_route(
        self,
        graph: nx.MultiDiGraph,
        start_node_id: str,
        end_node_id: Optional[str] = None,
        via_nodes: Optional[List[str]] = None,
        preferences: Optional[dict] = None,
        avoid_difficult: bool = False
    ) -> Route:
        """
        Plan a hiking route through the trail network.

        Args:
            graph: Trail network graph
            start_node_id: Starting node ID
            end_node_id: Ending node ID (None for loop)
            via_nodes: Optional list of intermediate nodes to visit
            preferences: Cost function preferences
            avoid_difficult: Avoid difficult trails

        Returns:
            Route object

        Raises:
            NoValidPathError: If no valid path found
        """
        # Update cost function preferences
        if preferences:
            for key, value in preferences.items():
                self.cost_function.set_preference(key, value)

        if avoid_difficult:
            self.cost_function.optimize_for_easy()

        # Build node sequence
        if via_nodes:
            node_sequence = [start_node_id] + via_nodes
            if end_node_id:
                node_sequence.append(end_node_id)
            else:
                node_sequence.append(start_node_id)  # Loop back
        else:
            if end_node_id:
                node_sequence = [start_node_id, end_node_id]
            else:
                # Simple loop - find interesting nearby waypoint and return
                waypoint = self._find_loop_waypoint(graph, start_node_id)
                node_sequence = [start_node_id, waypoint, start_node_id]

        # Find path through all nodes
        all_segments = []
        waypoints = []

        for i in range(len(node_sequence) - 1):
            source = node_sequence[i]
            target = node_sequence[i + 1]

            segments = self._find_path_between_nodes(
                graph, source, target, avoid_difficult
            )

            if not segments:
                raise NoValidPathError(f"No path found between {source} and {target}")

            all_segments.extend(segments)

            # Add intermediate nodes as waypoints
            for seg in segments:
                node = seg.end_node
                if node.node_type.value in ['peak', 'shelter', 'hut', 'viewpoint']:
                    if node not in waypoints:
                        waypoints.append(node)

        # Recalculate elevation gain/loss from the same profile source used by
        # the elevation chart (segment geometry + node fallback interpolation).
        for segment in all_segments:
            seg_gain, seg_loss = self._calculate_segment_elevation_gain_loss(segment)
            segment.elevation_gain = seg_gain
            segment.elevation_loss = seg_loss

        # Calculate totals
        total_distance = sum(s.distance for s in all_segments)
        total_elev_gain, total_elev_loss = self._calculate_route_elevation_gain_loss(all_segments)

        # Determine overall difficulty (max of all segments)
        max_difficulty = max(s.difficulty for s in all_segments)

        # Create route
        route = Route(
            route_id=str(uuid.uuid4()),
            segments=all_segments,
            total_distance=total_distance,
            total_elevation_gain=total_elev_gain,
            total_elevation_loss=total_elev_loss,
            estimated_time=0.0,  # Will be filled by estimation service
            difficulty=max_difficulty,
            waypoints=waypoints,
            is_loop=(end_node_id is None or end_node_id == start_node_id)
        )

        return route

    def _calculate_route_elevation_gain_loss(
        self,
        segments: List[RouteSegment]
    ) -> Tuple[float, float]:
        """Calculate route-level gain/loss on a globally-smoothed full profile."""
        if not segments:
            return 0.0, 0.0

        # Collect raw per-segment profiles (unsmoothed) then smooth the whole route.
        # Use Optional[float] so None nodes don't become 0.
        raw: List[Optional[float]] = []
        for segment in segments:
            seg = self._build_raw_segment_profile(segment)
            if not raw:
                raw.extend(seg)
            elif len(seg) > 1:
                raw.extend(seg[1:])

        # Linear interpolation over None gaps before smoothing
        raw = self._interpolate_none(raw)

        # Apply aggressive global smoothing before accumulating gain/loss
        smoothed = self._filter_elevation_outliers(raw, window=25, threshold=200.0, passes=3)
        smoothed = self._smooth_elevation_profile(smoothed, half_win=15)
        return self._calculate_gain_loss_from_profile(smoothed)

    @staticmethod
    def _interpolate_none(profile: List[Optional[float]]) -> List[float]:
        """Linear interpolation over None gaps; edge gaps use nearest valid value."""
        n = len(profile)
        out: List[float] = [v if v is not None else float('nan') for v in profile]
        valid = [i for i, v in enumerate(profile) if v is not None]
        if not valid:
            return [0.0] * n
        for i in range(n):
            if profile[i] is not None:
                continue
            lo = next((j for j in reversed(valid) if j < i), None)
            hi = next((j for j in valid if j > i), None)
            if lo is not None and hi is not None:
                out[i] = profile[lo] + (profile[hi] - profile[lo]) * (i - lo) / (hi - lo)
            elif lo is not None:
                out[i] = profile[lo]
            else:
                out[i] = profile[hi]
        return out

    def _build_raw_segment_profile(self, segment: RouteSegment) -> List[float]:
        """Build raw (unsmoothed) elevation profile for a segment."""
        geom = segment.geometry

        def geom_elev(pt):
            return float(pt[2]) if pt and len(pt) >= 3 and pt[2] is not None else None

        def first_e(g):
            if not g:
                return None
            for p in g:
                e = geom_elev(p)
                if e is not None:
                    return e
            return None

        def last_e(g):
            if not g:
                return None
            for p in reversed(g):
                e = geom_elev(p)
                if e is not None:
                    return e
            return None

        interp_start = first_e(geom) or segment.start_node.elevation  # may be None
        interp_end   = last_e(geom)  or segment.end_node.elevation    # may be None

        if not geom or len(geom) <= 1:
            return [interp_start, interp_end]  # type: ignore[list-item]

        n = len(geom)
        profile: List[Optional[float]] = [interp_start]
        for idx, point in enumerate(geom):
            if idx == 0:
                continue
            e = geom_elev(point)
            if e is None and interp_start is not None and interp_end is not None:
                e = interp_start + (interp_end - interp_start) * idx / (n - 1)
            profile.append(e)
        return profile  # type: ignore[return-value]

    def _calculate_segment_elevation_gain_loss(
        self,
        segment: RouteSegment
    ) -> Tuple[float, float]:
        """Calculate segment gain/loss on a smoothed profile."""
        raw = self._interpolate_none(self._build_raw_segment_profile(segment))
        smoothed = self._filter_elevation_outliers(raw, window=25, threshold=200.0, passes=3)
        smoothed = self._smooth_elevation_profile(smoothed, half_win=15)
        return self._calculate_gain_loss_from_profile(smoothed)

    def _build_segment_elevation_profile(self, segment: RouteSegment) -> List[float]:
        """Build elevation profile for a segment mirroring frontend elevation profile logic."""
        geom = segment.geometry

        def geom_elev(pt):
            return float(pt[2]) if pt and len(pt) >= 3 and pt[2] is not None else None

        def first_geom_elev(g):
            if not g:
                return None
            for pt in g:
                e = geom_elev(pt)
                if e is not None:
                    return e
            return None

        def last_geom_elev(g):
            if not g:
                return None
            for pt in reversed(g):
                e = geom_elev(pt)
                if e is not None:
                    return e
            return None

        interp_start = first_geom_elev(geom) or float(segment.start_node.elevation or 0.0)
        interp_end   = last_geom_elev(geom)  or float(segment.end_node.elevation   or 0.0)

        if not geom or len(geom) <= 1:
            return [interp_start, interp_end]

        num_points = len(geom)
        profile = [interp_start]
        for idx, point in enumerate(geom):
            if idx == 0:
                continue
            e = geom_elev(point)
            if e is None:
                e = interp_start + (interp_end - interp_start) * idx / (num_points - 1)
            profile.append(e)

        # Remove gross DEM outliers then smooth remaining noise
        profile = self._filter_elevation_outliers(profile)
        profile = self._smooth_elevation_profile(profile)
        return profile

    @staticmethod
    def _smooth_elevation_profile(profile: List[float], half_win: int = 5) -> List[float]:
        """Gaussian-weighted moving average matching the frontend smoothing."""
        import math
        n = len(profile)
        if n <= 2:
            return profile
        sigma = half_win / 2.0
        weights = [math.exp(-(k * k) / (2 * sigma * sigma)) for k in range(-half_win, half_win + 1)]
        result = []
        for i in range(n):
            v_sum = w_sum = 0.0
            for k in range(-half_win, half_win + 1):
                j = i + k
                if 0 <= j < n:
                    w = weights[k + half_win]
                    v_sum += profile[j] * w
                    w_sum += w
            result.append(v_sum / w_sum)
        return result

    @staticmethod
    def _filter_elevation_outliers(
        profile: List[float], window: int = 25, threshold: float = 200.0, passes: int = 3
    ) -> List[float]:
        """Replace points deviating >threshold from local median with the median value."""
        data = profile[:]
        for _ in range(passes):
            result = data[:]
            for i in range(len(data)):
                lo = max(0, i - window)
                hi = min(len(data), i + window + 1)
                neighbors = sorted(data[lo:hi])
                median = neighbors[len(neighbors) // 2]
                if abs(data[i] - median) > threshold:
                    result[i] = median
            data = result
        return data

    def _calculate_gain_loss_from_profile(self, elevations: List[float]) -> Tuple[float, float]:
        """Calculate gain/loss from ordered elevation values."""
        if len(elevations) < 2:
            return 0.0, 0.0

        gain = 0.0
        loss = 0.0
        threshold = 1.0  # profile is pre-smoothed; count all persistent changes

        for i in range(1, len(elevations)):
            diff = elevations[i] - elevations[i - 1]
            if diff > threshold:
                gain += diff
            elif diff < -threshold:
                loss += abs(diff)

        return gain, loss

    def _find_path_between_nodes(
        self,
        graph: nx.MultiDiGraph,
        source_id: str,
        target_id: str,
        avoid_difficult: bool = False
    ) -> List[RouteSegment]:
        """
        Find shortest path between two nodes using A*.

        Args:
            graph: Trail network graph
            source_id: Source node ID
            target_id: Target node ID
            avoid_difficult: Avoid difficult trails

        Returns:
            List of RouteSegment objects
        """
        # Define weight function for pathfinding
        def weight_fn(u, v, d):
            # For MultiDiGraph, d is a dict of {key: edge_data}
            # We need to extract the actual edge data from the first key
            if isinstance(d, dict) and len(d) > 0:
                # Get edge data from first key (handles parallel edges)
                first_key = next(iter(d))
                edge_data = d[first_key]
                
                # Now check for 'data' attribute
                if 'data' not in edge_data:
                    logger.warning(f"Edge {u}->{v} (key={first_key}) missing 'data' attribute, using default cost")
                    return 10.0
                
                edge: Edge = edge_data['data']
            else:
                logger.warning(f"Edge {u}->{v} has unexpected format: {type(d)}, using default cost")
                return 10.0
            
            if avoid_difficult:
                return self.cost_function.adjust_for_avoid_difficult(edge)
            return self.cost_function.calculate_edge_cost(edge)

        # Define heuristic for A*
        def heuristic_fn(u, v):
            node_u: Node = graph.nodes[u]['data']
            node_v: Node = graph.nodes[v]['data']
            return self.cost_function.calculate_heuristic(
                node_u.lat, node_u.lon,
                node_v.lat, node_v.lon
            )

        try:
            # Use A* algorithm
            path = nx.astar_path(
                graph,
                source_id,
                target_id,
                heuristic=heuristic_fn,
                weight=weight_fn
            )
        except nx.NetworkXNoPath:
            logger.warning(f"No path found between {source_id} and {target_id}")
            return []
        except Exception as e:
            logger.error(f"Error finding path: {e}")
            return []

        # Convert path to segments
        segments = []
        for i in range(len(path) - 1):
            u = path[i]
            v = path[i + 1]

            # Get edge data (use first edge if multiple)
            edge_data = graph.get_edge_data(u, v)
            if edge_data:
                # Get first edge
                first_key = list(edge_data.keys())[0]
                edge: Edge = edge_data[first_key]['data']

                start_node: Node = graph.nodes[u]['data']
                end_node: Node = graph.nodes[v]['data']

                segment = RouteSegment(
                    start_node=start_node,
                    end_node=end_node,
                    edge=edge,
                    distance=edge.distance / 1000.0,  # Convert to km
                    elevation_gain=edge.elevation_gain,
                    elevation_loss=edge.elevation_loss,
                    estimated_time=0.0,  # Will be filled by estimation service
                    difficulty=edge.difficulty,
                    geometry=edge.geometry
                )
                segments.append(segment)

        return segments

    def _find_loop_waypoint(
        self,
        graph: nx.MultiDiGraph,
        start_node_id: str,
        max_distance: float = 10.0
    ) -> str:
        """
        Find an interesting waypoint for a loop route.

        Args:
            graph: Trail network graph
            start_node_id: Starting node
            max_distance: Maximum distance in km

        Returns:
            Node ID of waypoint
        """
        start_node: Node = graph.nodes[start_node_id]['data']

        # Prefer peaks and viewpoints
        candidates = []

        for node_id, data in graph.nodes(data=True):
            if node_id == start_node_id:
                continue

            node: Node = data['data']

            # Calculate distance
            from app.utils.geo_utils import haversine_distance
            dist = haversine_distance(
                start_node.lat, start_node.lon,
                node.lat, node.lon
            ) / 1000.0  # Convert to km

            if dist > max_distance:
                continue

            # Score waypoint (prefer peaks and viewpoints)
            score = 0
            if node.node_type.value == 'peak':
                score = 100
            elif node.node_type.value == 'viewpoint':
                score = 80
            elif node.node_type.value == 'hut':
                score = 50
            else:
                score = 10

            # Prefer moderate distance (not too close, not too far)
            dist_score = max(0, 10 - abs(dist - max_distance / 2))
            score += dist_score

            candidates.append((node_id, score))

        if not candidates:
            # Fallback: find any reachable node
            for node_id in graph.nodes():
                if node_id != start_node_id:
                    return node_id

        # Sort by score and return best
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def optimize_route_for_scenic(self, route: Route, graph: nx.MultiDiGraph) -> Route:
        """
        Re-optimize existing route to prefer scenic points.

        Args:
            route: Existing route
            graph: Trail network graph

        Returns:
            Optimized route
        """
        self.cost_function.optimize_for_scenic()

        # Re-route with scenic preferences
        start_id = route.segments[0].start_node.id
        end_id = route.segments[-1].end_node.id

        return self.plan_route(graph, start_id, end_id)
