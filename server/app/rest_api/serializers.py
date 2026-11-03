from typing import Any, Dict, List

import json

from pydantic import BaseModel, Field, field_validator

from app.settings import get_settings

settings = get_settings()
MAX_PAYLOAD_SIZE_BYTES = settings.MAX_PAYLOAD_SIZE_BYTES


class HealthCheck(BaseModel):
    status: str = Field(default="OK", examples=["OK"])


class StoreOrderRequest(BaseModel):
    """Request model for storing checkout order"""

    data: Dict[str, Any] = Field(..., description="JSON-LD order data")

    @field_validator("data")
    @classmethod
    def validate_data(cls, v):
        if not v:
            raise ValueError("Order data cannot be empty")
        data_size = len(json.dumps(v).encode("utf-8"))
        if data_size > MAX_PAYLOAD_SIZE_BYTES:
            raise ValueError(
                f"Payload size ({data_size} bytes) exceeds maximum allowed "
                f"({MAX_PAYLOAD_SIZE_BYTES} bytes)"
            )
        datasets = v.get("dcat:dataset")
        if datasets is None:
            raise ValueError("'dcat:dataset' is required.")
        if not isinstance(datasets, list):
            raise ValueError("'dcat:dataset' must be a list.")
        if not datasets:
            raise ValueError("'dcat:dataset' cannot be empty.")
        for idx, dataset in enumerate(datasets):
            if "region" not in dataset:
                raise ValueError(f"Dataset at index {idx} missing 'region'.")
            if "dcat:distribution" not in dataset or not isinstance(
                dataset["dcat:distribution"], list
            ):
                raise ValueError(
                    f"Dataset at index {idx} missing 'dcat:distribution' list."
                )
            for didx, dist in enumerate(dataset["dcat:distribution"]):
                if "dcat:accessURL" not in dist:
                    raise ValueError(
                        f"Distribution at index {didx} in dataset {idx} "
                        f"missing 'dcat:accessURL'."
                    )
        return v


class StoreOrderResponse(BaseModel):
    """Response model for store operation"""

    order_id: str = Field(..., description="UUID of the stored order")
    expires_in_seconds: int = Field(..., description="TTL in seconds")


class RetrieveOrderResponse(BaseModel):
    """Response model for retrieve operation"""

    order_id: str
    data: List[Dict[str, Any]] = Field(..., description="Array of dataset objects")
