"""Tests for orders API endpoints."""

from typing import Any

import base64
import json
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

        # Mock the usecase to return transformed data structure
        # (what the usecase actually returns)
        transformed_data = {
            "data": [
                {
                    "region": "EU",
                    "distribution": [
                        {
                            "accessURL": (
                                "https://ds-connector.EU.nextgen.hiro-develop.nl/"
                                "distribution-content/https/example.com/data1.csv/chunk"
                            ),
                            "mediaType": "text/csv",
                        },
                        {
                            "accessURL": (
                                "https://ds-connector.EU.nextgen.hiro-develop.nl/"
                                "distribution-content/https/example.com/"
                                "data2.json/chunk"
                            ),
                            "mediaType": "application/json",
                        },
                    ],
                },
                {
                    "region": "US",
                    "distribution": [
                        {
                            "accessURL": (
                                "https://ds-connector.US.nextgen.hiro-develop.nl/"
                                "distribution-content/https/example.com/data3.xml/chunk"
                            ),
                            "mediaType": "application/xml",
                        },
                    ],
                },
            ],
            "metadata": {"created": "2023-01-01T00:00:00Z", "version": "1.0"},
        }
        mock_usecases.retrieve_order.return_value = transformed_data

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
        # The API should return only the data array, not the whole transformed structure
        assert response_data["data"] == transformed_data["data"]

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


class TestOrdersRoutesContracts:
    """Contracts issued when an order is stored, and returned with it."""

    @pytest.fixture
    def app_with(self):
        def make(mock_usecases):
            app = FastAPI()
            app.include_router(OrdersRoutes().router)
            app.dependency_overrides[get_usecase] = lambda: mock_usecases
            return app

        return make

    @pytest.fixture
    def order(self):
        return {
            "dcat:dataset": [
                {
                    "identifier": "a",
                    "title": "A",
                    "region": "hus",
                    "dcat:distribution": [{"dcat:accessURL": "https://x/a.csv"}],
                }
            ]
        }

    def test_issues_stores_and_returns_contracts(self, app_with, order, monkeypatch):
        from app.core.contracts import IssuedContract
        from app.rest_api.routes import orders as orders_module
        from app.settings import ContractGeneratorSettings

        monkeypatch.setattr(
            orders_module.settings,
            "CONTRACT_GENERATORS",
            {"HUS": ContractGeneratorSettings(url="http://gen", node_id="hus.node")},
        )
        calls = {}

        async def fake_issue(**kwargs):
            calls.update(kwargs)
            return [IssuedContract(region="hus", jti="j-1", token="t.o.k")]

        monkeypatch.setattr(orders_module, "issue_contracts_for_order", fake_issue)
        mock_usecases = AsyncMock(spec=usecases.OrderUsecases)
        mock_usecases.store_order.return_value = ("order-1", 7200)

        claims = {
            "sub": "EAID",
            "email": "researcher@hus.example",
            "role": "researcher",
        }
        token = ".".join(
            base64.urlsafe_b64encode(json.dumps(part).encode()).decode().rstrip("=")
            for part in ({"alg": "RS256"}, claims)
        )
        with TestClient(app_with(mock_usecases)) as client:
            response = client.post(
                "/orders",
                json={"data": order},
                headers={"Authorization": f"Bearer {token}.sig"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["contracts"] == [
            {"region": "hus", "jti": "j-1", "token": "t.o.k"}
        ]
        assert calls["consumer_id"] == "researcher@hus.example"
        assert calls["ttl_seconds"] == 7200
        assert set(calls["generators"]) == {"hus"}  # region keys lowercased
        mock_usecases.store_contracts.assert_awaited_once_with(
            "order-1", [{"region": "hus", "jti": "j-1", "token": "t.o.k"}], 7200
        )

    def test_order_succeeds_when_no_contract_could_be_issued(
        self, app_with, order, monkeypatch
    ):
        from app.rest_api.routes import orders as orders_module
        from app.settings import ContractGeneratorSettings

        monkeypatch.setattr(
            orders_module.settings,
            "CONTRACT_GENERATORS",
            {"hus": ContractGeneratorSettings(url="http://gen", node_id="hus.node")},
        )
        default_consumer = orders_module.settings.CONTRACT_DEFAULT_CONSUMER_ID

        async def none_issued(**kwargs):
            assert kwargs["consumer_id"] == default_consumer
            return []

        monkeypatch.setattr(orders_module, "issue_contracts_for_order", none_issued)
        mock_usecases = AsyncMock(spec=usecases.OrderUsecases)
        mock_usecases.store_order.return_value = ("order-2", 7200)

        with TestClient(app_with(mock_usecases)) as client:
            response = client.post("/orders", json={"data": order})

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["contracts"] == []
        mock_usecases.store_contracts.assert_not_awaited()

    def test_order_succeeds_when_storing_contracts_fails(
        self, app_with, order, monkeypatch
    ):
        from app.core.contracts import IssuedContract
        from app.rest_api.routes import orders as orders_module
        from app.settings import ContractGeneratorSettings

        monkeypatch.setattr(
            orders_module.settings,
            "CONTRACT_GENERATORS",
            {"hus": ContractGeneratorSettings(url="http://gen", node_id="hus.node")},
        )

        async def one_issued(**kwargs):
            return [IssuedContract(region="hus", jti="j", token="t")]

        monkeypatch.setattr(orders_module, "issue_contracts_for_order", one_issued)
        mock_usecases = AsyncMock(spec=usecases.OrderUsecases)
        mock_usecases.store_order.return_value = ("order-3", 7200)
        mock_usecases.store_contracts.side_effect = RuntimeError("redis down")

        with TestClient(app_with(mock_usecases)) as client:
            response = client.post("/orders", json={"data": order})

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["order_id"] == "order-3"

    def test_no_generators_configured_means_no_contracts(
        self, app_with, order, monkeypatch
    ):
        from app.rest_api.routes import orders as orders_module

        monkeypatch.setattr(orders_module.settings, "CONTRACT_GENERATORS", {})

        async def must_not_run(**kwargs):
            raise AssertionError("no generator is configured")

        monkeypatch.setattr(orders_module, "issue_contracts_for_order", must_not_run)
        mock_usecases = AsyncMock(spec=usecases.OrderUsecases)
        mock_usecases.store_order.return_value = ("order-4", 7200)

        with TestClient(app_with(mock_usecases)) as client:
            response = client.post("/orders", json={"data": order})

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["contracts"] == []

    def test_retrieve_returns_the_stored_contracts(self, app_with):
        mock_usecases = AsyncMock(spec=usecases.OrderUsecases)
        mock_usecases.retrieve_order.return_value = {"data": [{"identifier": "a"}]}
        mock_usecases.retrieve_contracts.return_value = [
            {"region": "hus", "jti": "j-1", "token": "t.o.k"}
        ]

        with TestClient(app_with(mock_usecases)) as client:
            response = client.get(f"/orders/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["contracts"] == [
            {"region": "hus", "jti": "j-1", "token": "t.o.k"}
        ]
