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
    async def retrieve_order(self, order_id: str) -> Optional[Any]:
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

    async def retrieve_order(self, order_id: str) -> Optional[Any]:
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

            # Apply URL mapping to the flattened data
            mapped_json = self._apply_url_mapping(plain_json)

            return mapped_json

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

        This function only handles JSON-LD to flat JSON transformation.
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
            # Create result with cleaned graph data and preserve other top-level fields
            cleaned_result = {"data": cleaned_items}

            # Preserve other top-level fields (like metadata)
            for key, value in data.items():
                if key != "@graph":  # Skip the graph field we already processed
                    clean_key = key.split(":")[-1] if ":" in key else key
                    clean_key = clean_key.replace("@", "")
                    cleaned_result[clean_key] = await self._clean_value(value)

            cleaned_result = await self._clean_extra_metadata_prefixes(cleaned_result)
        # Handle dcat:dataset structure
        elif "dcat:dataset" in data:
            datasets = data["dcat:dataset"]
            cleaned_items = await asyncio.gather(
                *(self._clean_value(item) for item in datasets)
            )
            # Create result with cleaned dataset data and preserve other fields
            cleaned_result = {"data": cleaned_items}

            # Preserve other top-level fields (like metadata)
            for key, value in data.items():
                if key != "dcat:dataset":  # Skip the dataset field we already processed
                    clean_key = key.split(":")[-1] if ":" in key else key
                    clean_key = clean_key.replace("@", "")
                    cleaned_result[clean_key] = await self._clean_value(value)

            cleaned_result = await self._clean_extra_metadata_prefixes(cleaned_result)
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

        # Process single dataset item with extraMetadata
        if "extraMetadata" in data and isinstance(data["extraMetadata"], dict):
            cleaned_meta = {}
            for key, value in data["extraMetadata"].items():
                new_key = re.sub(uri_prefix_pattern, "", key)
                cleaned_meta[new_key] = value
            data["extraMetadata"] = cleaned_meta

        # Process dataset lists (for backwards compatibility)
        if "dataset" in data and isinstance(data["dataset"], list):
            for ds in data["dataset"]:
                extra = ds.get("extraMetadata")
                if isinstance(extra, dict):
                    cleaned_meta = {}
                    for key, value in extra.items():
                        new_key = re.sub(uri_prefix_pattern, "", key)
                        cleaned_meta[new_key] = value
                    ds["extraMetadata"] = cleaned_meta

        # Process data array (for dcat:dataset structure)
        if "data" in data and isinstance(data["data"], list):
            for item in data["data"]:
                if isinstance(item, dict):
                    # Recursively clean each item
                    await self._clean_extra_metadata_prefixes(item)

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

    def _apply_url_mapping(self, flattened_data: Any) -> Any:
        """
        Apply URL mapping to flattened JSON data.

        This wrapper function handles URL mapping after JSON-LD transformation.

        Args:
            flattened_data: The flattened JSON data from _jsonld_to_json

        Returns:
            Any: Data with mapped URLs
        """
        if not isinstance(flattened_data, dict):
            return flattened_data

        logger.debug(
            f"Applying URL mapping to data with keys: {list(flattened_data.keys())}"
        )

        # Check if this has a "data" field with a list of items
        # (from @graph or dcat:dataset)
        if "data" in flattened_data and isinstance(flattened_data["data"], list):
            logger.debug(f"Found data array with {len(flattened_data['data'])} items")
            # Map URLs for each item in the list
            for item in flattened_data["data"]:
                if isinstance(item, dict):
                    self.map_urls_in_dataset_item(item)
        # Check if this has a "data" field with a "dataset" array (nested structure)
        elif "data" in flattened_data and isinstance(flattened_data["data"], dict):
            logger.debug("Found nested data structure")
            if "dataset" in flattened_data["data"] and isinstance(
                flattened_data["data"]["dataset"], list
            ):
                logger.debug(
                    f"Found dataset array with "
                    f"{len(flattened_data['data']['dataset'])} items"
                )
                # Map URLs for each dataset item
                for dataset_item in flattened_data["data"]["dataset"]:
                    if isinstance(dataset_item, dict):
                        self.map_urls_in_dataset_item(dataset_item)
        else:
            logger.debug("Single item, mapping directly")
            # Single item, map it directly
            self.map_urls_in_dataset_item(flattened_data)

        return flattened_data

    def map_access_url(self, access_url: str, region: str) -> str:
        """
        Map access URL based on region and protocol.

        Example:
        - Input: "file://genetic_analysis_part0/client_2.h5ad",
                 region: "uva"
        - Output: "https://ds-connector.uva.nextgen.hiro-develop.nl/"
                  "distribution-content/"
                  "file/genetic_analysis_part0/client_2.h5ad/chunk"

        Args:
            access_url: Original access URL
                       (e.g., "file://genetic_analysis_part0/client_2.h5ad")
            region: Region code ("uva", "ki", "hus")

        Returns:
            str: Mapped accessible URL
        """
        if not access_url or not region:
            return access_url

        # Parse protocol and path
        if "://" in access_url:
            protocol, path = access_url.split("://", 1)
        else:
            return access_url  # Return unchanged if no protocol

        # Build mapped URL based on protocol
        base_url = settings.DS_CONNECTOR_BASE_URL.format(region=region)

        if protocol == "file":
            mapped_url = f"{base_url}/file/{path}/chunk"
        elif protocol == "s3":
            mapped_url = f"{base_url}/s3/{path}/chunk"
        else:
            # For other protocols, use generic mapping
            mapped_url = f"{base_url}/{protocol}/{path}/chunk"

        return mapped_url

    def map_urls_in_dataset_item(self, dataset_item: Any) -> None:
        """
        Map access URLs in a single dataset item.

        This modifies the dataset_item in place.
        Each dataset item has its own region and distribution array.

        Args:
            dataset_item: Single dataset item
        """
        if not isinstance(dataset_item, dict):
            logger.debug("Dataset item is not a dict, skipping URL mapping")
            return

        # Get region from the dataset item
        region = dataset_item.get("region")
        if not region:
            logger.debug("No region found in dataset item, skipping URL mapping")
            return  # No region, skip mapping

        logger.debug(f"Mapping URLs for region: {region}")

        # Process distribution array if it exists (cleaned name from dcat:distribution)
        if "distribution" in dataset_item and isinstance(
            dataset_item["distribution"], list
        ):
            logger.debug(
                f"Found {len(dataset_item['distribution'])} distributions to process"
            )
            for distribution in dataset_item["distribution"]:
                if isinstance(distribution, dict):
                    # Check for accessURL (cleaned from dcat:accessURL)
                    if "accessURL" in distribution:
                        original_url = distribution["accessURL"]
                        mapped_url = self.map_access_url(original_url, region)
                        distribution["accessURL"] = mapped_url
                        logger.info(
                            f"Mapped accessURL: {original_url} -> {mapped_url} "
                            f"(region: {region})"
                        )
                else:
                    logger.debug("Distribution item is not a dict")
        else:
            logger.debug("No distribution array found in dataset item")

    def map_urls_in_flattened_data(self, data: Any) -> Any:
        """
        Map access URLs in flattened data based on region.

        This is for backward compatibility with simpler data structures.

        Args:
            data: Flattened JSON data containing region and distribution with accessURL

        Returns:
            Any: Data with mapped URLs
        """
        if not isinstance(data, dict):
            return data

        # Get region from data
        region = data.get("region")
        if not region:
            return data  # No region, return unchanged

        # Create a copy of the data to modify
        result = data.copy()

        # Process distribution array if it exists
        if "distribution" in result and isinstance(result["distribution"], list):
            for distribution in result["distribution"]:
                if isinstance(distribution, dict) and "accessURL" in distribution:
                    original_url = distribution["accessURL"]
                    mapped_url = self.map_access_url(original_url, region)
                    distribution["accessURL"] = mapped_url
                    logger.debug(f"Mapped URL: {original_url} -> {mapped_url}")

        return result
