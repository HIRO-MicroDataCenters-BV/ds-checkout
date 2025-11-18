"""Tests for OrderUsecases business logic."""


import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.repository.repositories import RedisRepository
from app.core.usecases import OrderUsecases


class TestOrderUsecases:
    """Test OrderUsecases business logic."""

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        return AsyncMock(spec=RedisRepository)

    @pytest.fixture
    def usecases(self, mock_repository):
        """Create OrderUsecases instance with mock repository."""
        return OrderUsecases(mock_repository)

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
                        }
                    ],
                }
            ],
            "metadata": {"created": "2023-01-01T00:00:00Z", "version": "1.0"},
        }

    @pytest.mark.asyncio
    async def test_store_order_success(
        self, usecases, mock_repository, sample_order_data
    ):
        """Test successfully storing an order."""
        # Setup
        mock_repository.store.return_value = True

        # Execute
        order_id, ttl = await usecases.store_order(sample_order_data)

        # Verify
        assert isinstance(order_id, str)
        assert len(order_id) == 36  # UUID length
        uuid.UUID(order_id)  # Validate it's a proper UUID
        assert isinstance(ttl, int)
        assert ttl > 0

        # Verify repository was called correctly
        mock_repository.store.assert_called_once()
        call_args = mock_repository.store.call_args
        assert call_args[0][0] == order_id  # order_id
        assert call_args[0][1] == sample_order_data  # order_data
        assert call_args[0][2] == ttl  # ttl

    @pytest.mark.asyncio
    async def test_store_order_repository_failure(
        self, usecases, mock_repository, sample_order_data
    ):
        """Test handling repository storage failure."""
        # Setup
        mock_repository.store.return_value = False

        # Execute & Verify
        with pytest.raises(Exception, match="Failed to store order"):
            await usecases.store_order(sample_order_data)

        # Verify repository was called
        mock_repository.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_order_repository_exception(
        self, usecases, mock_repository, sample_order_data
    ):
        """Test handling repository exceptions during storage."""
        # Setup
        mock_repository.store.side_effect = Exception("Redis connection failed")

        # Execute & Verify
        with pytest.raises(Exception, match="Redis connection failed"):
            await usecases.store_order(sample_order_data)

        # Verify repository was called
        mock_repository.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_order_success(
        self, usecases, mock_repository, sample_order_data
    ):
        """Test successfully retrieving an order."""
        # Setup
        order_id = str(uuid.uuid4())
        mock_repository.retrieve.return_value = sample_order_data

        # Execute
        result = await usecases.retrieve_order(order_id)

        # Verify - the result should be transformed from JSON-LD to plain JSON
        # The transformation removes 'dcat:' prefixes, so dcat:dataset becomes dataset
        expected_transformed = {
            "dataset": [
                {
                    "region": "EU",
                    "distribution": [
                        {
                            "accessURL": "https://example.com/data1.csv",
                            "mediaType": "text/csv",
                        }
                    ],
                }
            ],
            "metadata": {"created": "2023-01-01T00:00:00Z", "version": "1.0"},
        }
        assert result == expected_transformed
        mock_repository.retrieve.assert_called_once_with(order_id)

    @pytest.mark.asyncio
    async def test_retrieve_order_not_found(self, usecases, mock_repository):
        """Test retrieving non-existent order returns None."""
        # Setup
        order_id = str(uuid.uuid4())
        mock_repository.retrieve.return_value = None

        # Execute
        result = await usecases.retrieve_order(order_id)

        # Verify
        assert result is None
        mock_repository.retrieve.assert_called_once_with(order_id)

    @pytest.mark.asyncio
    async def test_retrieve_order_repository_exception(self, usecases, mock_repository):
        """Test handling repository exceptions during retrieval."""
        # Setup
        order_id = str(uuid.uuid4())
        mock_repository.retrieve.side_effect = Exception("Redis connection failed")

        # Execute & Verify
        with pytest.raises(Exception, match="Redis connection failed"):
            await usecases.retrieve_order(order_id)

        # Verify repository was called
        mock_repository.retrieve.assert_called_once_with(order_id)

    @pytest.mark.asyncio
    async def test_delete_order_success(self, usecases, mock_repository):
        """Test successfully deleting an order."""
        # Setup
        order_id = str(uuid.uuid4())
        mock_repository.delete.return_value = True

        # Execute
        result = await usecases.delete_order(order_id)

        # Verify
        assert result is True
        mock_repository.delete.assert_called_once_with(order_id)

    @pytest.mark.asyncio
    async def test_delete_order_not_found(self, usecases, mock_repository):
        """Test deleting non-existent order returns False."""
        # Setup
        order_id = str(uuid.uuid4())
        mock_repository.delete.return_value = False

        # Execute
        result = await usecases.delete_order(order_id)

        # Verify
        assert result is False
        mock_repository.delete.assert_called_once_with(order_id)

    @pytest.mark.asyncio
    async def test_delete_order_repository_exception(self, usecases, mock_repository):
        """Test handling repository exceptions during deletion."""
        # Setup
        order_id = str(uuid.uuid4())
        mock_repository.delete.side_effect = Exception("Redis connection failed")

        # Execute & Verify
        with pytest.raises(Exception, match="Redis connection failed"):
            await usecases.delete_order(order_id)

        # Verify repository was called
        mock_repository.delete.assert_called_once_with(order_id)

    @pytest.mark.asyncio
    async def test_store_order_generates_unique_ids(
        self, usecases, mock_repository, sample_order_data
    ):
        """Test that store_order generates unique UUIDs for different calls."""
        # Setup
        mock_repository.store.return_value = True

        # Execute multiple times
        order_id_1, _ = await usecases.store_order(sample_order_data)
        order_id_2, _ = await usecases.store_order(sample_order_data)
        order_id_3, _ = await usecases.store_order(sample_order_data)

        # Verify all IDs are unique
        assert order_id_1 != order_id_2
        assert order_id_2 != order_id_3
        assert order_id_1 != order_id_3

        # Verify all are valid UUIDs
        uuid.UUID(order_id_1)
        uuid.UUID(order_id_2)
        uuid.UUID(order_id_3)

    @pytest.mark.asyncio
    async def test_store_order_with_complex_data(self, usecases, mock_repository):
        """Test storing order with complex nested data structure."""
        # Setup complex order data
        complex_order_data = {
            "dcat:dataset": [
                {
                    "region": "EU",
                    "dcat:distribution": [
                        {
                            "dcat:accessURL": "https://example.com/data1.csv",
                            "dcat:mediaType": "text/csv",
                            "dcat:byteSize": 1024,
                            "dcat:format": "CSV",
                            "metadata": {
                                "columns": ["id", "name", "value"],
                                "rows": 100,
                            },
                        }
                    ],
                    "additional_metadata": {
                        "source": "Dataset Provider",
                        "license": "CC-BY-4.0",
                        "tags": ["research", "science"],
                    },
                }
            ],
            "order_metadata": {
                "user_id": "user123",
                "session_id": "session456",
                "timestamp": "2023-01-01T12:00:00Z",
            },
        }

        mock_repository.store.return_value = True

        # Execute
        order_id, ttl = await usecases.store_order(complex_order_data)

        # Verify
        assert isinstance(order_id, str)
        uuid.UUID(order_id)  # Validate UUID format
        assert isinstance(ttl, int)

        # Verify repository was called with correct data
        mock_repository.store.assert_called_once()
        call_args = mock_repository.store.call_args
        assert call_args[0][1] == complex_order_data
