"""Tests for orders API endpoints."""

from typing import Any

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.core import usecases
from app.rest_api.routes.orders import OrdersRoutes, get_usecase


class TestOrdersRoutes:
    """Test orders API endpoints."""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client."""
        routes = OrdersRoutes()
        app = FastAPI()
        app.include_router(routes.router)

        with TestClient(app) as client:
            yield client

    @pytest.fixture
    def sample_order_data(self):
        """Sample order data for testing."""
        return {
            "dcat:dataset": [
                {
                    "region": "EU",
                    "dcat:distribution": [
                        {
                            "dcat:accessURL": "https://example.com/data1.csv",
                            "dcat:mediaType": "text/csv",
                        },
                        {
                            "dcat:accessURL": "https://example.com/data2.json",
                            "dcat:mediaType": "application/json",
                        },
                    ],
                },
                {
                    "region": "US",
                    "dcat:distribution": [
                        {
                            "dcat:accessURL": "https://example.com/data3.xml",
                            "dcat:mediaType": "application/xml",
                        }
                    ],
                },
            ],
            "metadata": {"created": "2023-01-01T00:00:00Z", "version": "1.0"},
        }

    @pytest.fixture
    def mock_usecases(self):
        """Create mock usecases."""
        return AsyncMock(spec=usecases.OrderUsecases)

    @pytest.fixture(autouse=True)
    def setup_and_cleanup_dependencies(self):
        """Automatically clean up dependency overrides after each test."""
        yield
        # Cleanup after each test - This would be handled by FastAPI app
        # but since we're testing in isolation, we note it here

    def override_usecases_dependency(self, app: FastAPI, mock_usecases: Any) -> None:
        """Helper method to override the get_usecase dependency."""
        app.dependency_overrides[get_usecase] = lambda: mock_usecases

    def test_store_order_success(self, client, sample_order_data, mock_usecases):
        """Test successfully storing an order."""
        # Setup
        order_id = str(uuid.uuid4())
        ttl = 3600
        mock_usecases.store_order.return_value = (order_id, ttl)

        # Create app with dependency override
        routes = OrdersRoutes()
        app = FastAPI()
        app.include_router(routes.router)
        self.override_usecases_dependency(app, mock_usecases)

        with TestClient(app) as test_client:
            # Make request
            response = test_client.post("/orders", json={"data": sample_order_data})

        # Verify
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["order_id"] == order_id
        assert response_data["expires_in_seconds"] == ttl

        # Verify usecase was called correctly
        mock_usecases.store_order.assert_called_once_with(sample_order_data)

    def test_store_order_with_empty_data_fails(self, client, mock_usecases):
        """Test storing order with empty data fails validation."""
        # Setup
        routes = OrdersRoutes()
        app = FastAPI()
        app.include_router(routes.router)
        self.override_usecases_dependency(app, mock_usecases)

        with TestClient(app) as test_client:
            # Make request with empty data
            response = test_client.post("/orders", json={"data": {}})

        # Verify validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_store_order_usecase_exception_returns_500(
        self, client, sample_order_data, mock_usecases
    ):
        """Test that usecase exceptions return 500 error."""
        # Setup
        mock_usecases.store_order.side_effect = Exception("Database error")

        routes = OrdersRoutes()
        app = FastAPI()
        app.include_router(routes.router)
        self.override_usecases_dependency(app, mock_usecases)

        with TestClient(app) as test_client:
            # Make request
            response = test_client.post("/orders", json={"data": sample_order_data})

        # Verify
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        response_data = response.json()
        assert "Failed to store order" in response_data["detail"]

    def test_retrieve_order_success(self, client, sample_order_data, mock_usecases):
        """Test successfully retrieving an order."""
        # Setup
        order_id = str(uuid.uuid4())
        mock_usecases.retrieve_order.return_value = sample_order_data

        routes = OrdersRoutes()
        app = FastAPI()
        app.include_router(routes.router)
        self.override_usecases_dependency(app, mock_usecases)

        with TestClient(app) as test_client:
            # Make request
            response = test_client.get(f"/orders/{order_id}")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["order_id"] == order_id
        assert response_data["data"] == sample_order_data

        # Verify usecase was called correctly
        mock_usecases.retrieve_order.assert_called_once_with(order_id)

    def test_retrieve_order_not_found(self, client, mock_usecases):
        """Test retrieving non-existent order returns 404."""
        # Setup
        order_id = str(uuid.uuid4())
        mock_usecases.retrieve_order.return_value = None

        routes = OrdersRoutes()
        app = FastAPI()
        app.include_router(routes.router)
        self.override_usecases_dependency(app, mock_usecases)

        with TestClient(app) as test_client:
            # Make request
            response = test_client.get(f"/orders/{order_id}")

        # Verify
        assert response.status_code == status.HTTP_404_NOT_FOUND
        response_data = response.json()
        assert "not found or expired" in response_data["detail"]

    def test_retrieve_order_invalid_uuid_format(self, client, mock_usecases):
        """Test retrieving order with invalid UUID format returns 400."""
        # Setup
        invalid_order_id = "invalid-uuid-format"

        routes = OrdersRoutes()
        app = FastAPI()
        app.include_router(routes.router)
        self.override_usecases_dependency(app, mock_usecases)

        with TestClient(app) as test_client:
            # Make request
            response = test_client.get(f"/orders/{invalid_order_id}")

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "Invalid order_id format" in response_data["detail"]

        # Verify usecase was not called
        mock_usecases.retrieve_order.assert_not_called()

    def test_retrieve_order_usecase_exception_returns_500(self, client, mock_usecases):
        """Test that usecase exceptions during retrieval return 500 error."""
        # Setup
        order_id = str(uuid.uuid4())
        mock_usecases.retrieve_order.side_effect = Exception(
            "Database connection failed"
        )

        routes = OrdersRoutes()
        app = FastAPI()
        app.include_router(routes.router)
        self.override_usecases_dependency(app, mock_usecases)

        with TestClient(app) as test_client:
            # Make request
            response = test_client.get(f"/orders/{order_id}")

        # Verify
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        response_data = response.json()
        assert "Failed to retrieve order" in response_data["detail"]

    def test_store_order_invalid_json_structure(self, client, mock_usecases):
        """Test storing order with invalid JSON structure fails validation."""
        # Setup - missing required dcat:dataset
        invalid_data = {"metadata": {"version": "1.0"}}

        routes = OrdersRoutes()
        app = FastAPI()
        app.include_router(routes.router)
        self.override_usecases_dependency(app, mock_usecases)

        with TestClient(app) as test_client:
            # Make request
            response = test_client.post("/orders", json={"data": invalid_data})

        # Verify validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_store_order_missing_distribution_access_url(self, client, mock_usecases):
        """
        Test storing order with missing dcat:accessURL in distribution fails validation.
        """
        # Setup - missing dcat:accessURL
        invalid_data = {
            "dcat:dataset": [
                {
                    "region": "EU",
                    "dcat:distribution": [
                        {
                            "dcat:mediaType": "text/csv"
                            # Missing dcat:accessURL
                        }
                    ],
                }
            ]
        }

        routes = OrdersRoutes()
        app = FastAPI()
        app.include_router(routes.router)
        self.override_usecases_dependency(app, mock_usecases)

        with TestClient(app) as test_client:
            # Make request
            response = test_client.post("/orders", json={"data": invalid_data})

        # Verify validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_endpoints_have_correct_tags(self, client):
        """Test that endpoints are properly tagged for API documentation."""
        routes = OrdersRoutes()
        app = FastAPI()
        app.include_router(routes.router)

        # Check the OpenAPI schema for proper tags
        openapi_schema = app.openapi()
        paths = openapi_schema.get("paths", {})

        # Check store order endpoint has correct tag
        store_endpoint = paths.get("/orders", {}).get("post", {})
        assert "Orders" in store_endpoint.get("tags", [])

        # Check retrieve order endpoint has correct tag
        retrieve_endpoint = paths.get("/orders/{order_id}", {}).get("get", {})
        assert "Orders" in retrieve_endpoint.get("tags", [])
