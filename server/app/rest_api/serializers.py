from typing import Any, Dict

from pydantic import BaseModel, Field


class HealthCheck(BaseModel):
    status: str = Field(examples=["OK"])


class StoreOrderRequest(BaseModel):
    """Request model for storing checkout order"""

    data: Dict[str, Any] = Field(..., description="JSON-LD order data")
    # TODO: Add validation for JSON-LD structure


class StoreOrderResponse(BaseModel):
    """Response model for store operation"""

    order_id: str = Field(..., description="UUID of the stored order")
    expires_in_seconds: int = Field(..., description="TTL in seconds")


class RetrieveOrderResponse(BaseModel):
    """Response model for retrieve operation"""

    order_id: str
    data: Dict[str, Any]
