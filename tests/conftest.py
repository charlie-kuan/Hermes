"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_route_request():
    """Sample route planning request."""
    return {
        "area_id": "test_region",
        "start_lat": 23.45,
        "start_lon": 120.95,
        "loop_route": True,
        "max_distance": 15,
        "hiker_fitness": "moderate",
        "pack_weight_kg": 12.0
    }
