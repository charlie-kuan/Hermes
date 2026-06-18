"""Tests for elevation gain/loss calculation based on elevation profile geometry."""

import networkx as nx
import pytest

from app.models.domain import Edge, Node, NodeType, TrailDifficulty
from app.services.routing_service import RoutingService


def _node(node_id: str, elevation: float) -> Node:
    return Node(
        id=node_id,
        node_type=NodeType.INTERSECTION,
        lat=23.5,
        lon=120.9,
        elevation=elevation,
        name=node_id,
    )


def test_plan_route_uses_geometry_elevation_profile_for_gain_loss():
    graph = nx.MultiDiGraph()

    start = _node("A", 100.0)
    end = _node("B", 200.0)

    graph.add_node(start.id, data=start)
    graph.add_node(end.id, data=end)

    edge = Edge(
        source=start.id,
        target=end.id,
        distance=1000.0,
        elevation_gain=10.0,
        elevation_loss=5.0,
        difficulty=TrailDifficulty.MODERATE,
        geometry=[
            (23.5000, 120.9000, 100.0),
            (23.5001, 120.9001, 150.0),
            (23.5002, 120.9002, 120.0),
            (23.5003, 120.9003, 180.0),
            (23.5004, 120.9004, 200.0),
        ],
    )

    graph.add_edge(start.id, end.id, data=edge)

    service = RoutingService(graph_service=None)
    route = service.plan_route(graph, start.id, end.id)

    assert len(route.segments) == 1
    assert route.segments[0].elevation_gain == pytest.approx(130.0)
    assert route.segments[0].elevation_loss == pytest.approx(30.0)
    assert route.total_elevation_gain == pytest.approx(130.0)
    assert route.total_elevation_loss == pytest.approx(30.0)


def test_plan_route_falls_back_to_interpolated_profile_when_geometry_has_no_elevation():
    graph = nx.MultiDiGraph()

    start = _node("A", 100.0)
    end = _node("B", 200.0)

    graph.add_node(start.id, data=start)
    graph.add_node(end.id, data=end)

    edge = Edge(
        source=start.id,
        target=end.id,
        distance=1000.0,
        elevation_gain=999.0,
        elevation_loss=999.0,
        difficulty=TrailDifficulty.MODERATE,
        geometry=[
            (23.5000, 120.9000),
            (23.5001, 120.9001),
            (23.5002, 120.9002),
        ],
    )

    graph.add_edge(start.id, end.id, data=edge)

    service = RoutingService(graph_service=None)
    route = service.plan_route(graph, start.id, end.id)

    assert route.segments[0].elevation_gain == pytest.approx(100.0)
    assert route.segments[0].elevation_loss == pytest.approx(0.0)
    assert route.total_elevation_gain == pytest.approx(100.0)
    assert route.total_elevation_loss == pytest.approx(0.0)
