"""Tests for health check API endpoints."""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.rest_api.routes.health_check import HealthCheckRoutes


class TestHealthCheckRoutes:
    """Test health check API endpoints."""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client."""
        routes = HealthCheckRoutes()
        app = FastAPI()
        app.include_router(routes.router)

        with TestClient(app) as client:
            yield client

    def test_get_health_check_success(self, client):
        """Test getting health check status (no mocking needed for static data)."""
        # Make request
        response = client.get("/health-check/")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["status"] == "OK"
