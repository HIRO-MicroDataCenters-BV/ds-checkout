import logging
import uuid

from classy_fastapi import Routable, get, post
from fastapi import Depends, HTTPException, status

from app.core import usecases
from app.core.repository.repositories import RedisRepository
from app.rest_api.serializers import (
    RetrieveOrderResponse,
    StoreOrderRequest,
    StoreOrderResponse,
)

from ..depends import get_repository

logger = logging.getLogger(__name__)


def get_usecase(
    repository: RedisRepository = Depends(get_repository),
) -> usecases.OrderUsecases:
    return usecases.OrderUsecases(repository)


class OrdersRoutes(Routable):
    def __init__(self):
        super().__init__()

    @post(
        "/orders",
        status_code=status.HTTP_201_CREATED,
        name="store_order",
        tags=["Orders"],
        response_model=StoreOrderResponse,
        summary="Store checkout order",
    )
    async def store_order(
        self,
        request: StoreOrderRequest,
        usecases: usecases.OrderUsecases = Depends(get_usecase),
    ) -> StoreOrderResponse:
        """
        Store checkout order temporarily

        - Accepts JSON-LD format
        - Generates UUID
        - Stores in Redis with TTL
        - Returns order_id for retrieval
        """
        try:
            order_id, ttl = await usecases.store_order(request.data)

            return StoreOrderResponse(order_id=order_id, expires_in_seconds=ttl)

        except HTTPException:
            # Re-raise HTTPException as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error in store_order: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store order",
            )

    @get(
        "/orders/{order_id}",
        response_model=RetrieveOrderResponse,
        name="retrieve_order",
        tags=["Orders"],
        summary="Retrieve checkout order",
        status_code=status.HTTP_200_OK,
    )
    async def retrieve_order(
        self,
        order_id: str,
        usecases: usecases.OrderUsecases = Depends(get_usecase),
    ) -> RetrieveOrderResponse:
        """
        Retrieve checkout order by UUID

        - Retrieves from Redis
        - Transforms JSON-LD to plain JSON
        - Returns order data
        """
        try:
            # Validate UUID format
            try:
                uuid.UUID(order_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid order_id format",
                )

            data = await usecases.retrieve_order(order_id)

            if data is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {order_id} not found or expired",
                )

            return RetrieveOrderResponse(order_id=order_id, data=data)
        except HTTPException:
            # Re-raise HTTPException as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error in retrieve_order: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve order",
            )


routes = OrdersRoutes()
