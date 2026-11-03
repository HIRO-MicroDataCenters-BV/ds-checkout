from typing import Any, Dict, Optional

import json
import logging
from abc import ABC, abstractmethod

import redis.asyncio as redis

from app.database import DatabaseDriver
from app.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ORDER_KEY_PREFIX = settings.ORDER_KEY_PREFIX
ORDER_TTL_ENABLED = settings.ORDER_TTL_ENABLED


class Repositories(ABC):
    def __init__(self, db_driver: DatabaseDriver) -> None:
        ...

    @abstractmethod
    async def store(
        self, order_id: str, data: dict[str, Any], ttl_seconds: int
    ) -> bool:
        """Store data with a order_id and TTL"""
        ...

    @abstractmethod
    async def retrieve(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve data by order_id"""
        ...

    @abstractmethod
    async def delete(self, order_id: str) -> bool:
        """Delete data by order_id"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check connectivity to the database"""
        ...


class RedisRepository(Repositories):
    def __init__(self, db_driver: DatabaseDriver) -> None:
        self.redis_client = db_driver

    async def _get_key(self, order_id: str) -> str:
        """Generate Redis key for order"""
        return f"{ORDER_KEY_PREFIX}{order_id}"

    async def store(
        self, order_id: str, data: dict[str, Any], ttl_seconds: int
    ) -> bool:
        """
        Store order data in Redis with or without TTL

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            key = await self._get_key(order_id)
            serialized_data = json.dumps(data)

            if not ORDER_TTL_ENABLED:
                # Store without TTL
                result = await self.redis_client.set(name=key, value=serialized_data)
                logger.info(f"Stored order {order_id} without TTL")
                return bool(result)
            else:
                # Store with TTL
                result = await self.redis_client.setex(
                    name=key, time=ttl_seconds, value=serialized_data
                )
                logger.info(f"Stored order {order_id} with TTL {ttl_seconds}s")
                return bool(result)
        except redis.RedisError as e:
            logger.error(f"Redis error storing order {order_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error storing order {order_id}: {str(e)}")
            raise

    async def retrieve(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve order data from Redis

        Returns:
            Dict if found, None if not found
        """
        try:
            key = await self._get_key(order_id)
            data = await self.redis_client.get(key)

            if data is None:
                logger.warning(f"Order {order_id} not found or expired")
                return None

            # Deserialize JSON
            parsed_data: Dict[str, Any] = json.loads(data)
            logger.info(f"Retrieved order {order_id}")
            return parsed_data

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in Redis for order {order_id}: {str(e)}")
            raise
        except redis.RedisError as e:
            logger.error(f"Redis error retrieving order {order_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving order {order_id}: {str(e)}")
            raise

    async def delete(self, order_id: str) -> bool:
        """
        Delete order from Redis (optional, for one-time use cases)

        Returns:
            bool: True if deleted, False if not found
        """
        try:
            key = await self._get_key(order_id)
            result = await self.redis_client.delete(key)

            if result:
                logger.info(f"Deleted order {order_id}")
            return bool(result)

        except redis.RedisError as e:
            logger.error(f"Redis error deleting order {order_id}: {str(e)}")
            raise

    async def health_check(self) -> bool:
        """Check Redis connectivity"""
        try:
            result = await self.redis_client.ping()
            return bool(result)
        except redis.RedisError:
            return False
