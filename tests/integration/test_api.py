"""Integration tests for API endpoints."""

import pytest


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client):
        """Test health endpoint returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data


class TestAreasEndpoint:
    """Test areas endpoints."""

    def test_list_areas(self, client):
        """Test listing available areas."""
        response = client.get("/api/v1/areas")

        assert response.status_code == 200
        data = response.json()
        assert "areas" in data
        assert "total" in data
        assert isinstance(data["areas"], list)

    def test_get_area(self, client):
        """Test getting specific area."""
        # First get list of areas
        response = client.get("/api/v1/areas")
        areas = response.json()["areas"]

        if areas:
            area_id = areas[0]["area_id"]

            # Get specific area
            response = client.get(f"/api/v1/areas/{area_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["area_id"] == area_id
            assert "name" in data
            assert "bbox" in data

    def test_get_nonexistent_area(self, client):
        """Test getting non-existent area returns 404."""
        response = client.get("/api/v1/areas/nonexistent_area")

        assert response.status_code == 404


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data
