"""Cart HTTP API. Carts are keyed by user id."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.modules.cart.schemas import AddItem, CartView
from app.modules.cart.service import CartService
from app.modules.pricing.projections import ProductPriceProjectionWriter
from app.modules.products.projections import ProductProjectionWriter
from app.shared.deps import RedisDep, SessionDep

router = APIRouter(prefix="/users/{user_id}/cart", tags=["cart"])


def get_service(session: SessionDep, redis: RedisDep) -> CartService:
    return CartService(session, ProductProjectionWriter(redis), ProductPriceProjectionWriter(redis))


ServiceDep = Annotated[CartService, Depends(get_service)]


@router.get("", response_model=CartView)
async def get_cart(user_id: str, service: ServiceDep) -> CartView:
    return await service.view(user_id)


@router.post("/items", response_model=CartView, status_code=status.HTTP_201_CREATED)
async def add_item(user_id: str, data: AddItem, service: ServiceDep) -> CartView:
    return await service.add_item(user_id, data)


@router.delete("/items/{product_id}", response_model=CartView)
async def remove_item(user_id: str, product_id: str, service: ServiceDep) -> CartView:
    return await service.remove_item(user_id, product_id)
