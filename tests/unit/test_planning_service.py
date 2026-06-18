"""Tests for multi-day planning split behavior."""

import networkx as nx

from app.models.domain import Edge, Node, NodeType, Route, RouteSegment, TrailDifficulty
from app.services.estimation_service import EstimationService
from app.services.planning_service import PlanningService


def _node(node_id: str, node_type: NodeType) -> Node:
    return Node(
        id=node_id,
        node_type=node_type,
        lat=23.5,
        lon=120.9,
        elevation=3000,
        name=node_id
    )


def _segment(start: Node, end: Node, hours: float) -> RouteSegment:
    return RouteSegment(
        start_node=start,
        end_node=end,
        edge=Edge(
            source=start.id,
            target=end.id,
            distance=1000,
            elevation_gain=100,
            elevation_loss=50,
            difficulty=TrailDifficulty.MODERATE,
        ),
        distance=1.0,
        elevation_gain=100,
        elevation_loss=50,
        estimated_time=hours,
        difficulty=TrailDifficulty.MODERATE,
    )


def test_split_days_only_at_route_overnight_nodes():
    planning_service = PlanningService(graph_service=None, estimation_service=EstimationService())

    start = _node("start", NodeType.TRAILHEAD)
    mid = _node("mid", NodeType.INTERSECTION)
    hut = _node("hut", NodeType.HUT)
    mid2 = _node("mid2", NodeType.INTERSECTION)
    end = _node("end", NodeType.PEAK)

    segments = [
        _segment(start, mid, 2.0),
        _segment(mid, hut, 2.0),
        _segment(hut, mid2, 1.0),
        _segment(mid2, end, 2.0),
    ]

    route = Route(
        route_id="r1",
        segments=segments,
        total_distance=4.0,
        total_elevation_gain=400,
        total_elevation_loss=200,
        estimated_time=7.0,
        difficulty=TrailDifficulty.MODERATE,
        waypoints=[],
    )

    plan = planning_service.split_into_days(
        route=route,
        graph=nx.MultiDiGraph(),
        target_hours_per_day=4.0,
    )

    assert plan.total_days == 2
    assert len(plan.days) == 2
    assert len(plan.overnight_stops) == 1
    assert plan.overnight_stops[0].id == "hut"
    assert plan.days[0].overnight_stop is not None
    assert plan.days[0].overnight_stop.id == "hut"


def test_no_split_without_overnight_node_even_if_time_threshold_reached():
    planning_service = PlanningService(graph_service=None, estimation_service=EstimationService())

    start = _node("start", NodeType.TRAILHEAD)
    mid = _node("mid", NodeType.INTERSECTION)
    view = _node("view", NodeType.VIEWPOINT)
    end = _node("end", NodeType.PEAK)

    segments = [
        _segment(start, mid, 2.0),
        _segment(mid, view, 2.0),
        _segment(view, end, 2.0),
    ]

    route = Route(
        route_id="r2",
        segments=segments,
        total_distance=3.0,
        total_elevation_gain=300,
        total_elevation_loss=150,
        estimated_time=6.0,
        difficulty=TrailDifficulty.MODERATE,
        waypoints=[],
    )

    plan = planning_service.split_into_days(
        route=route,
        graph=nx.MultiDiGraph(),
        target_hours_per_day=4.0,
    )

    assert plan.total_days == 1
    assert len(plan.days) == 1
    assert len(plan.overnight_stops) == 0
    assert plan.days[0].overnight_stop is None
