"""Tests for Pydantic serializers/models."""


import json

import pytest
from pydantic import ValidationError

from app.rest_api.serializers import (
    HealthCheck,
    RetrieveOrderResponse,
    StoreOrderRequest,
    StoreOrderResponse,
)


class TestHealthCheckSerializer:
    """Test HealthCheck serializer."""

    def test_health_check_valid_data(self):
        """Test HealthCheck with valid data."""
        health_check = HealthCheck(status="OK")
        assert health_check.status == "OK"

    def test_health_check_default_example(self):
        """Test HealthCheck default example."""
        health_check = HealthCheck()
        assert hasattr(health_check, "status")

    def test_health_check_serialization(self):
        """Test HealthCheck serialization to dict."""
        health_check = HealthCheck(status="OK")
        data = health_check.model_dump()
        assert data == {"status": "OK"}


class TestStoreOrderRequestSerializer:
    """Test StoreOrderRequest serializer."""

    @pytest.fixture
    def valid_order_data(self):
        """Valid order data for testing."""
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
            ]
        }

    def test_store_order_request_valid(self, valid_order_data):
        """Test StoreOrderRequest with valid data."""
        request = StoreOrderRequest(data=valid_order_data)
        assert request.data == valid_order_data

    def test_store_order_request_empty_data_fails(self):
        """Test StoreOrderRequest fails with empty data."""
        with pytest.raises(ValidationError, match="Order data cannot be empty"):
            StoreOrderRequest(data={})

    def test_store_order_request_none_data_fails(self):
        """Test StoreOrderRequest fails with None data."""
        with pytest.raises((ValidationError, TypeError)):
            StoreOrderRequest(data=None)  # type: ignore[arg-type]

    def test_store_order_request_missing_dcat_dataset(self):
        """Test StoreOrderRequest fails without dcat:dataset."""
        invalid_data = {"metadata": {"version": "1.0"}}
        with pytest.raises(ValidationError, match="'dcat:dataset' is required"):
            StoreOrderRequest(data=invalid_data)

    def test_store_order_request_dcat_dataset_not_list(self):
        """Test StoreOrderRequest fails when dcat:dataset is not a list."""
        invalid_data = {"dcat:dataset": "not a list"}
        with pytest.raises(ValidationError, match="'dcat:dataset' must be a list"):
            StoreOrderRequest(data=invalid_data)

    def test_store_order_request_missing_region(self):
        """Test StoreOrderRequest fails when dataset missing region."""
        invalid_data = {
            "dcat:dataset": [
                {
                    # Missing region
                    "dcat:distribution": [
                        {"dcat:accessURL": "https://example.com/data.csv"}
                    ]
                }
            ]
        }
        with pytest.raises(ValidationError, match="missing 'region'"):
            StoreOrderRequest(data=invalid_data)

    def test_store_order_request_missing_distribution(self):
        """Test StoreOrderRequest fails when dataset missing distribution."""
        invalid_data = {
            "dcat:dataset": [
                {
                    "region": "EU"
                    # Missing dcat:distribution
                }
            ]
        }
        with pytest.raises(ValidationError, match="missing 'dcat:distribution' list"):
            StoreOrderRequest(data=invalid_data)

    def test_store_order_request_distribution_not_list(self):
        """Test StoreOrderRequest fails when distribution is not a list."""
        invalid_data = {
            "dcat:dataset": [{"region": "EU", "dcat:distribution": "not a list"}]
        }
        with pytest.raises(ValidationError, match="missing 'dcat:distribution' list"):
            StoreOrderRequest(data=invalid_data)

    def test_store_order_request_missing_access_url(self):
        """Test StoreOrderRequest fails when distribution missing accessURL."""
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
        with pytest.raises(ValidationError, match="missing 'dcat:accessURL'"):
            StoreOrderRequest(data=invalid_data)

    def test_store_order_request_multiple_datasets_valid(self, valid_order_data):
        """Test StoreOrderRequest with multiple valid datasets."""
        request = StoreOrderRequest(data=valid_order_data)
        assert len(request.data["dcat:dataset"]) == 2
        assert request.data["dcat:dataset"][0]["region"] == "EU"
        assert request.data["dcat:dataset"][1]["region"] == "US"

    def test_store_order_request_complex_data_structure(self):
        """Test StoreOrderRequest with complex nested data."""
        complex_data = {
            "dcat:dataset": [
                {
                    "region": "EU",
                    "dcat:distribution": [
                        {
                            "dcat:accessURL": "https://example.com/data.csv",
                            "dcat:mediaType": "text/csv",
                            "dcat:byteSize": 1024,
                            "metadata": {
                                "columns": ["id", "name"],
                                "encoding": "utf-8",
                            },
                        }
                    ],
                    "additional_info": {"source": "Provider", "license": "MIT"},
                }
            ],
            "order_metadata": {
                "user": "test_user",
                "timestamp": "2023-01-01T00:00:00Z",
            },
        }

        request = StoreOrderRequest(data=complex_data)
        assert request.data == complex_data

    @pytest.mark.skip(reason="Payload size validation depends on settings")
    def test_store_order_request_large_payload_fails(self):
        """Test StoreOrderRequest fails with payload exceeding size limit."""
        # This test would need to be configured based on MAX_PAYLOAD_SIZE_BYTES setting
        large_data = {
            "dcat:dataset": [
                {
                    "region": "EU",
                    "dcat:distribution": [
                        {
                            "dcat:accessURL": "https://example.com/data.csv",
                            "large_field": "x" * 1000000,  # Very large field
                        }
                    ],
                }
            ]
        }

        # This would fail if payload exceeds configured limit
        with pytest.raises(ValidationError, match="Payload size.*exceeds maximum"):
            StoreOrderRequest(data=large_data)


class TestStoreOrderResponseSerializer:
    """Test StoreOrderResponse serializer."""

    def test_store_order_response_valid(self):
        """Test StoreOrderResponse with valid data."""
        response = StoreOrderResponse(
            order_id="550e8400-e29b-41d4-a716-446655440000", expires_in_seconds=3600
        )
        assert response.order_id == "550e8400-e29b-41d4-a716-446655440000"
        assert response.expires_in_seconds == 3600

    def test_store_order_response_missing_fields(self):
        """Test StoreOrderResponse fails with missing required fields."""
        with pytest.raises(ValidationError):
            StoreOrderResponse(
                order_id="test-id", expires_in_seconds=None  # type: ignore[arg-type]
            )

        with pytest.raises(ValidationError):
            StoreOrderResponse(
                order_id=None, expires_in_seconds=3600  # type: ignore[arg-type]
            )

    def test_store_order_response_serialization(self):
        """Test StoreOrderResponse serialization."""
        response = StoreOrderResponse(
            order_id="test-order-123", expires_in_seconds=7200
        )

        data = response.model_dump()
        expected = {"order_id": "test-order-123", "expires_in_seconds": 7200}
        assert data == expected

    def test_store_order_response_json_serialization(self):
        """Test StoreOrderResponse JSON serialization."""
        response = StoreOrderResponse(
            order_id="test-order-123", expires_in_seconds=7200
        )

        json_str = response.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["order_id"] == "test-order-123"
        assert parsed["expires_in_seconds"] == 7200


class TestRetrieveOrderResponseSerializer:
    """Test RetrieveOrderResponse serializer."""

    @pytest.fixture
    def sample_retrieved_data(self):
        """Sample retrieved order data - datasets array that the API returns."""
        return [
            {
                "region": "EU",
                "distribution": [
                    {
                        "accessURL": (
                            "https://ds-connector.EU.nextgen.hiro-develop.nl/"
                            "distribution-content/https/example.com/data.csv/chunk"
                        ),
                        "mediaType": "text/csv",
                    }
                ],
            }
        ]

    def test_retrieve_order_response_valid(self, sample_retrieved_data):
        """Test RetrieveOrderResponse with valid data."""
        response = RetrieveOrderResponse(
            order_id="550e8400-e29b-41d4-a716-446655440000", data=sample_retrieved_data
        )
        assert response.order_id == "550e8400-e29b-41d4-a716-446655440000"
        assert response.data == sample_retrieved_data

    def test_retrieve_order_response_missing_fields(self, sample_retrieved_data):
        """Test RetrieveOrderResponse fails with missing required fields."""
        with pytest.raises(ValidationError):
            RetrieveOrderResponse(
                order_id="test-id", data=None  # type: ignore[arg-type]
            )

        with pytest.raises(ValidationError):
            RetrieveOrderResponse(
                order_id=None, data=sample_retrieved_data  # type: ignore[arg-type]
            )

    def test_retrieve_order_response_empty_data(self):
        """Test RetrieveOrderResponse with empty data list."""
        response = RetrieveOrderResponse(order_id="test-order-123", data=[])
        assert response.order_id == "test-order-123"
        assert response.data == []

    def test_retrieve_order_response_complex_data(self):
        """Test RetrieveOrderResponse with complex data structure."""
        complex_data = [
            {
                "region": "Global",
                "distribution": [
                    {
                        "accessURL": (
                            "https://ds-connector.Global.nextgen.hiro-develop.nl/"
                            "distribution-content/https/api.example.com/data/chunk"
                        ),
                        "mediaType": "application/json",
                        "authentication": {
                            "type": "bearer",
                            "token_url": "https://auth.example.com/token",
                        },
                    }
                ],
                "processing": {
                    "transformations": ["normalize", "aggregate"],
                    "output_format": "parquet",
                },
                "tracking": {"request_id": "req-123", "user_session": "session-456"},
            }
        ]

        response = RetrieveOrderResponse(
            order_id="complex-order-789", data=complex_data
        )

        assert response.order_id == "complex-order-789"
        assert response.data == complex_data

    def test_retrieve_order_response_serialization(self, sample_retrieved_data):
        """Test RetrieveOrderResponse serialization."""
        response = RetrieveOrderResponse(
            order_id="test-order-123", data=sample_retrieved_data
        )

        data = response.model_dump()
        expected = {"order_id": "test-order-123", "data": sample_retrieved_data}
        assert data == expected

    def test_retrieve_order_response_json_serialization(self, sample_retrieved_data):
        """Test RetrieveOrderResponse JSON serialization."""
        response = RetrieveOrderResponse(
            order_id="test-order-123", data=sample_retrieved_data
        )

        json_str = response.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["order_id"] == "test-order-123"
        assert parsed["data"] == sample_retrieved_data


class TestSerializerIntegration:
    """Test serializers working together in integration scenarios."""

    def test_store_and_retrieve_order_flow(self):
        """Test complete flow from store request to retrieve response."""
        # Original order data (what gets stored)
        original_data = {
            "dcat:dataset": [
                {
                    "region": "EU",
                    "dcat:distribution": [
                        {
                            "dcat:accessURL": "https://example.com/data.csv",
                            "dcat:mediaType": "text/csv",
                        }
                    ],
                }
            ]
        }

        # 1. Create store request
        store_request = StoreOrderRequest(data=original_data)
        assert store_request.data == original_data

        # 2. Simulate store response
        store_response = StoreOrderResponse(
            order_id="test-order-123", expires_in_seconds=3600
        )

        # 3. Create retrieve response with transformed data (what the API returns)
        # This simulates what happens after JSON-LD transformation and URL mapping
        transformed_datasets = [
            {
                "region": "EU",
                "distribution": [
                    {
                        "accessURL": (
                            "https://ds-connector.EU.nextgen.hiro-develop.nl/"
                            "distribution-content/https/example.com/data.csv/chunk"
                        ),
                        "mediaType": "text/csv",
                    }
                ],
            }
        ]

        retrieve_response = RetrieveOrderResponse(
            order_id=store_response.order_id, data=transformed_datasets
        )

        # Verify data consistency
        assert retrieve_response.order_id == store_response.order_id
        assert retrieve_response.data == transformed_datasets

    def test_serialization_round_trip(self):
        """Test serialization and deserialization round trip."""
        original_data = {
            "dcat:dataset": [
                {
                    "region": "US",
                    "dcat:distribution": [
                        {
                            "dcat:accessURL": "https://data.gov/dataset.json",
                            "dcat:mediaType": "application/json",
                        }
                    ],
                }
            ],
            "metadata": {"created_at": "2023-01-01T12:00:00Z", "version": "v2.0"},
        }

        # Store request
        store_request = StoreOrderRequest(data=original_data)
        store_json = store_request.model_dump_json()
        store_parsed = StoreOrderRequest.model_validate_json(store_json)

        assert store_parsed.data == original_data

        # Retrieve response with transformed data (what the API actually returns)
        transformed_datasets = [
            {
                "region": "US",
                "distribution": [
                    {
                        "accessURL": (
                            "https://ds-connector.US.nextgen.hiro-develop.nl/"
                            "distribution-content/https/data.gov/dataset.json/chunk"
                        ),
                        "mediaType": "application/json",
                    }
                ],
            }
        ]

        retrieve_response = RetrieveOrderResponse(
            order_id="test-123", data=transformed_datasets
        )
        retrieve_json = retrieve_response.model_dump_json()
        retrieve_parsed = RetrieveOrderResponse.model_validate_json(retrieve_json)

        assert retrieve_parsed.data == transformed_datasets
        assert retrieve_parsed.order_id == "test-123"
