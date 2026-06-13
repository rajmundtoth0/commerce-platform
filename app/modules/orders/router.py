"""Orders HTTP API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.modules.cart.service import CartService
from app.modules.orders.schemas import OrderRead
from app.modules.orders.service import OrderService
from app.modules.pricing.projections import ProductPriceProjectionWriter
from app.modules.products.projections import ProductProjectionWriter
from app.shared.deps import RedisDep, SessionDep
from app.shared.dto import Page

router = APIRouter(prefix="/users/{user_id}/orders", tags=["orders"])


def get_service(session: SessionDep, redis: RedisDep) -> OrderService:
    cart = CartService(session, ProductProjectionWriter(redis), ProductPriceProjectionWriter(redis))
    return OrderService(session, cart)


ServiceDep = Annotated[OrderService, Depends(get_service)]


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def checkout(user_id: str, service: ServiceDep) -> OrderRead:
    return OrderRead.model_validate(await service.checkout(user_id))


@router.get("", response_model=Page[OrderRead])
async def list_orders(
    user_id: str,
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[OrderRead]:
    items, total = await service.list_for_user(user_id, limit=limit, offset=offset)
    return Page[OrderRead](
        items=[OrderRead.model_validate(o) for o in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(user_id: str, order_id: str, service: ServiceDep) -> OrderRead:
    return OrderRead.model_validate(await service.get(order_id))
