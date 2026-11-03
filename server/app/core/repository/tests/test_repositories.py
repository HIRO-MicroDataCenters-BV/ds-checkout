"""Tests for RedisRepository data access layer."""

import json
from unittest.mock import AsyncMock

import pytest
import redis.asyncio as redis

from app.core.repository.repositories import RedisRepository
from app.settings import get_settings

settings = get_settings()


class TestRedisRepositoryUnit:
    """Unit tests with mocked Redis client."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client with all necessary methods."""
        mock = AsyncMock()
        mock.setex = AsyncMock()
        mock.set = AsyncMock()
        mock.get = AsyncMock()
        mock.delete = AsyncMock()
        mock.ping = AsyncMock()
        return mock

    @pytest.fixture
    def repository(self, mock_redis_client):
        """Create RedisRepository instance with mock client."""
        return RedisRepository(mock_redis_client)

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
        self, repository, mock_redis_client, sample_order_data
    ):
        """Test successfully storing an order in Redis."""
        # Setup
        order_id = "test-order-123"
        ttl_seconds = 3600
        mock_redis_client.setex.return_value = True

        # Execute
        result = await repository.store(order_id, sample_order_data, ttl_seconds)

        # Verify
        assert result is True

        # Verify Redis setex was called correctly
        mock_redis_client.setex.assert_called_once()
        call_args = mock_redis_client.setex.call_args

        # Check the key format (keyword arguments)
        assert call_args.kwargs["name"].startswith("order:")
        assert order_id in call_args.kwargs["name"]

        # Check TTL
        assert call_args.kwargs["time"] == ttl_seconds

        # Check data was JSON serialized
        stored_data = json.loads(call_args.kwargs["value"])
        assert stored_data == sample_order_data

    @pytest.mark.asyncio
    async def test_store_order_redis_exception(
        self, repository, mock_redis_client, sample_order_data
    ):
        """Test handling Redis exceptions during storage."""
        # Setup
        order_id = "test-order-123"
        ttl_seconds = 3600
        mock_redis_client.setex.side_effect = redis.RedisError("Connection failed")

        # Execute & Verify
        with pytest.raises(redis.RedisError, match="Connection failed"):
            await repository.store(order_id, sample_order_data, ttl_seconds)

    @pytest.mark.asyncio
    async def test_retrieve_order_success(
        self, repository, mock_redis_client, sample_order_data
    ):
        """Test successfully retrieving an order from Redis."""
        # Setup
        order_id = "test-order-123"
        mock_redis_client.get.return_value = json.dumps(sample_order_data).encode(
            "utf-8"
        )

        # Execute
        result = await repository.retrieve(order_id)

        # Verify
        assert result == sample_order_data

        # Verify Redis get was called correctly
        mock_redis_client.get.assert_called_once()
        call_args = mock_redis_client.get.call_args[0]
        assert call_args[0].startswith("order:")
        assert order_id in call_args[0]

    @pytest.mark.asyncio
    async def test_retrieve_order_not_found(self, repository, mock_redis_client):
        """Test retrieving non-existent order returns None."""
        # Setup
        order_id = "non-existent-order"
        mock_redis_client.get.return_value = None

        # Execute
        result = await repository.retrieve(order_id)

        # Verify
        assert result is None
        mock_redis_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_order_success(self, repository, mock_redis_client):
        """Test successfully deleting an order from Redis."""
        # Setup
        order_id = "test-order-123"
        mock_redis_client.delete.return_value = (
            1  # Redis returns number of deleted keys
        )

        # Execute
        result = await repository.delete(order_id)

        # Verify
        assert result is True
        mock_redis_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_success(self, repository, mock_redis_client):
        """Test successful health check."""
        # Setup
        mock_redis_client.ping.return_value = True

        # Execute
        result = await repository.health_check()

        # Verify
        assert result is True
        mock_redis_client.ping.assert_called_once()


@pytest.mark.integration
class TestRedisRepositoryIntegration:
    """Integration tests with real Redis database."""

    async def get_redis_client(self):
        """Get Redis client for testing."""
        client = redis.Redis(
            host=settings.test_database.host,
            port=settings.test_database.port,
            db=settings.test_database.db_number,  # Use test database
            decode_responses=False,  # Keep bytes for consistency
        )

        # Test connection
        try:
            await client.ping()
            return client
        except redis.RedisError:
            pytest.skip("Redis not available for integration tests")

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
    async def test_store_and_retrieve_order_real_redis(self, sample_order_data):
        """Test full store/retrieve cycle with real Redis."""
        redis_client = await self.get_redis_client()
        repository = RedisRepository(redis_client)

        try:
            order_id = "integration-test-order"
            ttl_seconds = 60  # Short TTL for testing

            # Store order
            store_result = await repository.store(
                order_id, sample_order_data, ttl_seconds
            )
            assert store_result is True

            # Retrieve order
            retrieved_data = await repository.retrieve(order_id)
            assert retrieved_data == sample_order_data

            # Verify TTL is set (should be positive and less than our original TTL)
            key = f"order:{order_id}"
            ttl = await redis_client.ttl(key)
            assert 0 < ttl <= ttl_seconds

        finally:
            # Cleanup
            await redis_client.flushdb()
            await redis_client.aclose()

    @pytest.mark.asyncio
    async def test_order_expiration_real_redis(self, sample_order_data):
        """Test that orders actually expire in Redis."""
        redis_client = await self.get_redis_client()
        repository = RedisRepository(redis_client)

        try:
            order_id = "expiring-test-order"
            ttl_seconds = 1  # Very short TTL

            # Store order with short TTL
            await repository.store(order_id, sample_order_data, ttl_seconds)

            # Should exist immediately
            result = await repository.retrieve(order_id)
            assert result == sample_order_data

            # Wait for expiration
            import asyncio

            await asyncio.sleep(2)

            # Should be expired now
            result = await repository.retrieve(order_id)
            assert result is None

        finally:
            # Cleanup
            await redis_client.flushdb()
            await redis_client.aclose()

    @pytest.mark.asyncio
    async def test_delete_order_real_redis(self, sample_order_data):
        """Test order deletion with real Redis."""
        redis_client = await self.get_redis_client()
        repository = RedisRepository(redis_client)

        try:
            order_id = "delete-test-order"

            # Store order
            await repository.store(order_id, sample_order_data, 3600)

            # Verify it exists
            result = await repository.retrieve(order_id)
            assert result is not None

            # Delete order
            delete_result = await repository.delete(order_id)
            assert delete_result is True

            # Verify it's gone
            result = await repository.retrieve(order_id)
            assert result is None

            # Delete non-existent order
            delete_result = await repository.delete("non-existent")
            assert delete_result is False

        finally:
            # Cleanup
            await redis_client.flushdb()
            await redis_client.aclose()

    @pytest.mark.asyncio
    async def test_large_data_serialization_real_redis(self):
        """Test storing and retrieving large complex data."""
        redis_client = await self.get_redis_client()
        repository = RedisRepository(redis_client)

        try:
            order_id = "large-data-test"

            # Create larger, more complex data
            large_data = {
                "dcat:dataset": [
                    {
                        "region": f"Region-{i}",
                        "dcat:distribution": [
                            {
                                "dcat:accessURL": (
                                    f"https://example.com/data{i}-{j}.csv"
                                ),
                                "dcat:mediaType": "text/csv",
                                "dcat:byteSize": 1024 * (i + 1),
                                "metadata": {
                                    "columns": [f"col_{k}" for k in range(10)],
                                    "encoding": "utf-8",
                                    "delimiter": ",",
                                    "nested_objects": {
                                        "quality_metrics": {
                                            "completeness": 0.95 + (i * 0.01),
                                            "accuracy": 0.98,
                                            "consistency": True,
                                        }
                                    },
                                },
                            }
                            for j in range(3)  # 3 distributions per dataset
                        ],
                    }
                    for i in range(5)  # 5 datasets
                ],
                "metadata": {
                    "version": "2.1",
                    "created_at": "2023-11-18T12:00:00Z",
                    "creator": "integration-test",
                    "tags": ["test", "integration", "large-data"],
                    "complex_nested": {
                        "level1": {"level2": {"level3": ["deep", "nesting", "test"]}}
                    },
                },
            }

            # Store and retrieve
            await repository.store(order_id, large_data, 3600)
            retrieved = await repository.retrieve(order_id)

            # Verify complex structure is preserved
            assert retrieved == large_data
            assert len(retrieved["dcat:dataset"]) == 5
            assert retrieved["metadata"]["complex_nested"]["level1"]["level2"][
                "level3"
            ] == ["deep", "nesting", "test"]

        finally:
            # Cleanup
            await redis_client.flushdb()
            await redis_client.aclose()
