from typing import Any, Dict, Optional

import asyncio
import json
import logging
import re
import uuid
from abc import ABC, abstractmethod

from app.core.repository.repositories import Repositories
from app.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
ORDER_TTL_SECONDS = settings.ORDER_TTL_SECONDS


class IUsecases(ABC):
    def __init__(self, repository: Repositories) -> None:
        self.repository = repository

    @abstractmethod
    async def store_order(self, order_data: Dict[str, Any]) -> tuple[str, int]:
        """Store checkout order temporarily"""
        ...

    @abstractmethod
    async def retrieve_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve stored checkout order by order_id"""
        ...

    @abstractmethod
    async def delete_order(self, order_id: str) -> bool:
        """Delete stored checkout order by order_id"""
        ...


class OrderUsecases(IUsecases):
    async def store_order(self, order_data: Dict[str, Any]) -> tuple[str, int]:
        """
        Store order and return order_id and TTL

        Returns:
            tuple: (order_id, ttl_seconds)
        """
        order_id = str(uuid.uuid4())
        ttl = ORDER_TTL_SECONDS

        try:
            success = await self.repository.store(order_id, order_data, ttl)
            if not success:
                raise Exception("Failed to store order in Redis")

            return order_id, ttl

        except Exception as e:
            logger.error(f"Service error storing order: {str(e)}")
            raise

    async def retrieve_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve order and transform from JSON-LD to plain JSON

        Returns:
            Dict if found, None if not found
        """
        try:
            data = await self.repository.retrieve(order_id)

            if data is None:
                return None

            # Transform JSON-LD to plain JSON
            plain_json = await self._jsonld_to_json(data)
            return plain_json

        except Exception as e:
            logger.error(f"Service error retrieving order {order_id}: {str(e)}")
            raise

    async def delete_order(self, order_id: str) -> bool:
        """
        Delete order by order_id

        Returns:
            bool: True if deleted, False if not found
        """
        try:
            result = await self.repository.delete(order_id)
            return result

        except Exception as e:
            logger.error(f"Service error deleting order {order_id}: {str(e)}")
            raise

    async def _jsonld_to_json(
        self, jsonld_data: Dict[str, Any] | str
    ) -> Dict[str, Any]:
        """
        Transform JSON-LD data to plain JSON

        This is a placeholder for actual transformation logic.
        """
        data: Dict[str, Any]
        if isinstance(jsonld_data, str):
            data = json.loads(jsonld_data)
        else:
            data = jsonld_data

        # Handle @graph structure
        if "@graph" in data:
            graphs = data["@graph"]
            cleaned_items = await asyncio.gather(
                *(self._clean_value(item) for item in graphs)
            )
            # Return a dict with cleaned graph data
            return {"data": cleaned_items}
        else:
            cleaned = await self._clean_value(data)

        # After base cleanup, handle extraMetadata prefixes
        cleaned_result = await self._clean_extra_metadata_prefixes(cleaned)
        return cleaned_result if isinstance(cleaned_result, dict) else {}

    async def _clean_extra_metadata_prefixes(self, data: Any) -> Any:
        """
        Remove URI-like prefixes (e.g. //oca.example.org/123/)
        from keys inside 'extraMetadata' fields across datasets.
        """
        uri_prefix_pattern = re.compile(
            r"^(\w+:)?//[^/]+/\d+/"
        )  # matches any URI/host prefix

        if not isinstance(data, dict):
            return data

        # Process dataset lists
        if "dataset" in data and isinstance(data["dataset"], list):
            for ds in data["dataset"]:
                extra = ds.get("extraMetadata")
                if isinstance(extra, dict):
                    cleaned_meta = {}
                    for key, value in extra.items():
                        new_key = re.sub(uri_prefix_pattern, "", key)
                        cleaned_meta[new_key] = value
                    ds["extraMetadata"] = cleaned_meta
        return data

    async def _clean_value(self, obj: Any) -> Any:
        """Extract clean values from JSON-LD structures."""
        if not isinstance(obj, dict):
            return obj

        # Handle @value objects
        if "@value" in obj:
            return obj["@value"]

        # Handle @id-only objects
        if list(obj.keys()) == ["@id"]:
            return obj["@id"]

        result = {}
        for key, value in obj.items():
            # Skip JSON-LD metadata keys
            if key in ("@context", "@type", "@id"):
                continue

            # Clean key: remove namespace prefixes and @ symbols
            clean_key = key.split(":")[-1] if ":" in key else key
            clean_key = clean_key.replace("@", "")

            # Recursively clean
            if isinstance(value, dict):
                cleaned = await self._clean_value(value)
                # Always keep isDeleted even if empty
                if clean_key.lower() == "isdeleted" or cleaned:
                    result[clean_key] = cleaned
            elif isinstance(value, list):
                cleaned_list = await asyncio.gather(
                    *(self._clean_value(item) for item in value)
                )
                cleaned_list = [item for item in cleaned_list if item not in ({}, None)]
                if cleaned_list:
                    result[clean_key] = cleaned_list
            else:
                result[clean_key] = value

        if not result:
            return None
        if any(k.lower() == "isdeleted" for k in result):
            return result

        return result if result else None
