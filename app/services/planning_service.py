"""Multi-day route planning service."""

from typing import List, Optional

from loguru import logger

from app.models.domain import DayPlan, MultiDayPlan, Node, NodeType, Route, RouteSegment
from app.services.estimation_service import EstimationService
from app.services.graph_service import GraphService
import networkx as nx


class PlanningService:
    """Handles multi-day route planning and splitting."""

    def __init__(
        self,
        graph_service: GraphService,
        estimation_service: EstimationService
    ):
        self.graph_service = graph_service
        self.estimation_service = estimation_service

    def split_into_days(
        self,
        route: Route,
        graph: nx.MultiDiGraph,
        target_hours_per_day: float = 7.0,
        prefer_huts: bool = True,
        fitness_level: str = "moderate",
        pack_weight_kg: float = 12.0
    ) -> MultiDayPlan:
        """
        Split a route into daily segments with overnight stops.

        Args:
            route: Complete route to split
            graph: Trail network graph
            target_hours_per_day: Target hiking hours per day
            prefer_huts: Prefer huts over campsites for overnight stops
            fitness_level: Hiker fitness level
            pack_weight_kg: Pack weight

        Returns:
            MultiDayPlan with daily segments and overnight stops
        """
        logger.info(f"Splitting route into multi-day plan (target: {target_hours_per_day}h/day)")

        # Ensure route has time estimates
        if route.segments[0].estimated_time == 0:
            route = self.estimation_service.estimate_all_segments(
                route, fitness_level, pack_weight_kg
            )

        # Calculate total time and estimate days needed
        total_time = route.estimated_time
        estimated_days = max(1, int(total_time / target_hours_per_day + 0.5))

        logger.info(f"Total time: {total_time:.1f}h, estimated days: {estimated_days}")

        # Split into days
        days = []
        current_day_segments = []
        cumulative_time = 0.0
        day_number = 1

        for i, segment in enumerate(route.segments):
            current_day_segments.append(segment)
            cumulative_time += segment.estimated_time

            # Check if we should end the day
            is_last_segment = (i == len(route.segments) - 1)
            should_split = (
                cumulative_time >= target_hours_per_day * 0.8 and  # At least 80% of target
                not is_last_segment
            )

            if should_split or is_last_segment:
                # Find overnight stop
                end_node = segment.end_node
                overnight_node = None

                if not is_last_segment:
                    # Find accommodation near current position
                    overnight_node = self._find_overnight_stop(
                        graph, end_node, prefer_huts
                    )

                # Create day plan
                day = self._create_day_plan(
                    day_number,
                    current_day_segments,
                    overnight_node
                )
                days.append(day)

                # Reset for next day
                current_day_segments = []
                cumulative_time = 0.0
                day_number += 1

        # Collect overnight stops
        overnight_stops = [day.overnight_stop for day in days if day.overnight_stop]

        multi_day_plan = MultiDayPlan(
            route=route,
            days=days,
            total_days=len(days),
            overnight_stops=overnight_stops
        )

        logger.info(f"Created {len(days)}-day plan with {len(overnight_stops)} overnight stops")

        return multi_day_plan

    def _find_overnight_stop(
        self,
        graph: nx.MultiDiGraph,
        current_node: Node,
        prefer_huts: bool
    ) -> Optional[Node]:
        """
        Find suitable overnight stop near current position.

        Args:
            graph: Trail network graph
            current_node: Current position
            prefer_huts: Prefer huts over campsites

        Returns:
            Overnight stop node or None
        """
        from app.utils.geo_utils import haversine_distance

        # Search radius: 2km
        max_distance = 2000  # meters

        candidates = []

        for node_id, data in graph.nodes(data=True):
            node: Node = data['data']

            # Check if suitable for overnight
            if node.node_type not in [NodeType.HUT, NodeType.CAMPSITE]:
                continue

            # Calculate distance from current node
            dist = haversine_distance(
                current_node.lat, current_node.lon,
                node.lat, node.lon
            )

            if dist > max_distance:
                continue

            # Score the candidate
            score = 0
            if node.node_type == NodeType.HUT:
                score = 100 if prefer_huts else 50
            elif node.node_type == NodeType.CAMPSITE:
                score = 50 if prefer_huts else 100

            # Prefer closer locations
            distance_score = max(0, 50 - (dist / 40))  # Max 50 points
            score += distance_score

            # Bonus for water availability
            if 'water' in node.amenities:
                score += 20

            candidates.append((node, score, dist))

        if not candidates:
            logger.warning(f"No overnight stop found near {current_node.id}")
            return None

        # Sort by score (highest first)
        candidates.sort(key=lambda x: x[1], reverse=True)

        best_node = candidates[0][0]
        logger.debug(f"Found overnight stop: {best_node.name or best_node.id} ({best_node.node_type.value})")

        return best_node

    def _create_day_plan(
        self,
        day_number: int,
        segments: List[RouteSegment],
        overnight_stop: Optional[Node]
    ) -> DayPlan:
        """
        Create a DayPlan from segments.

        Args:
            day_number: Day number
            segments: Route segments for this day
            overnight_stop: Overnight accommodation node

        Returns:
            DayPlan object
        """
        if not segments:
            raise ValueError("Cannot create day plan with no segments")

        start_node = segments[0].start_node
        end_node = segments[-1].end_node

        total_distance = sum(s.distance for s in segments)
        total_elev_gain = sum(s.elevation_gain for s in segments)
        total_elev_loss = sum(s.elevation_loss for s in segments)
        total_time = sum(s.estimated_time for s in segments)

        # Determine difficulty (max of all segments)
        max_difficulty = max(s.difficulty for s in segments)

        return DayPlan(
            day_number=day_number,
            segments=segments,
            start_node=start_node,
            end_node=end_node,
            total_distance=total_distance,
            total_elevation_gain=total_elev_gain,
            total_elevation_loss=total_elev_loss,
            estimated_time=total_time,
            difficulty=max_difficulty,
            overnight_stop=overnight_stop
        )

    def validate_day_plan(
        self,
        day_plan: DayPlan,
        min_hours: float = 3.0,
        max_hours: float = 12.0
    ) -> bool:
        """
        Validate that a day plan is reasonable.

        Args:
            day_plan: Day plan to validate
            min_hours: Minimum acceptable hours
            max_hours: Maximum acceptable hours

        Returns:
            True if valid, False otherwise
        """
        if day_plan.estimated_time < min_hours:
            logger.warning(f"Day {day_plan.day_number} too short: {day_plan.estimated_time:.1f}h")
            return False

        if day_plan.estimated_time > max_hours:
            logger.warning(f"Day {day_plan.day_number} too long: {day_plan.estimated_time:.1f}h")
            return False

        return True
