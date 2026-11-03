from typing import List, Optional

import logging
import uuid

from classy_fastapi import Routable, get, post
from fastapi import Depends, Header, HTTPException, status

from app.core import usecases
from app.core.contracts import (
    GeneratorTarget,
    consumer_from_bearer,
    issue_contracts_for_order,
)
from app.core.repository.repositories import RedisRepository
from app.rest_api.serializers import (
    OrderContract,
    RetrieveOrderResponse,
    StoreOrderRequest,
    StoreOrderResponse,
)
from app.settings import get_settings

from ..depends import get_repository

logger = logging.getLogger(__name__)
settings = get_settings()


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
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ) -> StoreOrderResponse:
        """
        Store checkout order temporarily

        - Accepts JSON-LD format
        - Generates UUID
        - Stores in Redis with TTL
        - Asks each region's contract generator for a contract covering that
          region's datasets (CONTRACT_GENERATORS); best effort
        - Returns order_id and the contracts issued

        The consumer named in a contract comes from the ds-login JWT in
        `Authorization: Bearer …` (its email, else keri:<AID>), which the
        website passes on. The token is read, not verified, until tokens are
        checked after the demo.
        """
        try:
            order_id, ttl = await usecases.store_order(request.data)

            contracts: List[OrderContract] = []
            if settings.CONTRACT_GENERATORS:
                issued = await issue_contracts_for_order(
                    order_id=order_id,
                    consumer_id=consumer_from_bearer(authorization)
                    or settings.CONTRACT_DEFAULT_CONSUMER_ID,
                    datasets=request.data.get("dcat:dataset") or [],
                    generators={
                        region.lower(): GeneratorTarget(
                            url=target.url, node_id=target.node_id
                        )
                        for region, target in settings.CONTRACT_GENERATORS.items()
                    },
                    ttl_seconds=ttl,
                )
                contracts = [
                    OrderContract(region=c.region, jti=c.jti, token=c.token)
                    for c in issued
                ]
                if contracts:
                    # Held beside the order, so whoever later retrieves the
                    # order with its order_id gets the contracts too. Best
                    # effort like issuing: the order is already stored.
                    try:
                        await usecases.store_contracts(
                            order_id, [c.model_dump() for c in contracts], ttl
                        )
                    except Exception as error:
                        logger.error(
                            "Order %s: contracts issued but not stored: %s",
                            order_id,
                            error,
                        )

            return StoreOrderResponse(
                order_id=order_id, expires_in_seconds=ttl, contracts=contracts
            )

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

            # Extract the datasets from the processed data structure
            datasets = data.get("data", []) if isinstance(data, dict) else []

            contracts = [
                OrderContract(**c) for c in await usecases.retrieve_contracts(order_id)
            ]

            return RetrieveOrderResponse(
                order_id=order_id, data=datasets, contracts=contracts
            )
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
