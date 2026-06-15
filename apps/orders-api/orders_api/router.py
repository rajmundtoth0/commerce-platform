from __future__ import annotations

from fastapi import APIRouter, Query, status

from orders_api.deps import AdminUser, CurrentUser, ServiceDep
from orders_api.schemas import OrderCreate, OrderRead

orders_router = APIRouter(prefix="/orders", tags=["orders"])


@orders_router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(data: OrderCreate, claims: CurrentUser, service: ServiceDep) -> OrderRead:
    order = await service.create(claims.sub, data)
    return OrderRead.model_validate(order)


@orders_router.get("", response_model=list[OrderRead])
async def list_orders(
    claims: CurrentUser,
    service: ServiceDep,
    user_id: str | None = Query(default=None),
) -> list[OrderRead]:
    # Customers may only see their own orders; admins may filter by user_id or
    # see all (when no user_id is supplied).
    effective_user_id = user_id if claims.role == "admin" else claims.sub
    orders = await service.list(user_id=effective_user_id)
    return [OrderRead.model_validate(o) for o in orders]


@orders_router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: str, claims: CurrentUser, service: ServiceDep) -> OrderRead:
    order = await service.get(order_id, claims.sub, is_admin=claims.role == "admin")
    return OrderRead.model_validate(order)


@orders_router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(order_id: str, claims: CurrentUser, service: ServiceDep) -> OrderRead:
    order = await service.transition(
        order_id, "cancelled", claims.sub, is_admin=claims.role == "admin"
    )
    return OrderRead.model_validate(order)


@orders_router.post("/{order_id}/pay", response_model=OrderRead)
async def pay_order(order_id: str, claims: AdminUser, service: ServiceDep) -> OrderRead:
    order = await service.transition(order_id, "paid", claims.sub, is_admin=True)
    return OrderRead.model_validate(order)


@orders_router.post("/{order_id}/ship", response_model=OrderRead)
async def ship_order(order_id: str, claims: AdminUser, service: ServiceDep) -> OrderRead:
    order = await service.transition(order_id, "shipped", claims.sub, is_admin=True)
    return OrderRead.model_validate(order)


@orders_router.post("/{order_id}/refund", response_model=OrderRead)
async def refund_order(order_id: str, claims: AdminUser, service: ServiceDep) -> OrderRead:
    order = await service.transition(order_id, "refunded", claims.sub, is_admin=True)
    return OrderRead.model_validate(order)
