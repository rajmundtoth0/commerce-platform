from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from cplatform.errors import ConflictError, ForbiddenError, NotFoundError
from orders_api.models import Order, OrderItem
from orders_api.schemas import OrderCreate
from orders_api.tasks import enqueue_order_summary

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Allowed status transitions. cancelled and refunded are terminal.
_TRANSITIONS: dict[str, set[str]] = {
    "created": {"paid", "cancelled"},
    "paid": {"shipped", "cancelled", "refunded"},
    "shipped": {"refunded"},
    "cancelled": set(),
    "refunded": set(),
}


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- commands --------------------------------------------------------
    async def create(self, user_id: str, data: OrderCreate) -> Order:
        items = [
            OrderItem(
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_amount_minor=item.unit_amount_minor,
            )
            for item in data.items
        ]
        total = sum(item.quantity * item.unit_amount_minor for item in data.items)
        order = Order(
            user_id=user_id,
            status="created",
            currency=data.currency,
            total_amount_minor=total,
            items=items,
        )
        self._session.add(order)
        await self._session.flush()
        enqueue_order_summary(order.id)
        return order

    async def transition(
        self, order_id: str, target: str, claims_sub: str, *, is_admin: bool
    ) -> Order:
        order = await self._get_owned(order_id, claims_sub, is_admin=is_admin)
        allowed = _TRANSITIONS.get(order.status, set())
        if target not in allowed:
            raise ConflictError(
                f"Cannot transition order from '{order.status}' to '{target}'",
                details={"order_id": order_id, "from": order.status, "to": target},
            )
        order.status = target
        await self._session.flush()
        enqueue_order_summary(order.id)
        return order

    # --- queries ---------------------------------------------------------
    async def get(self, order_id: str, claims_sub: str, *, is_admin: bool) -> Order:
        return await self._get_owned(order_id, claims_sub, is_admin=is_admin)

    async def list(self, *, user_id: str | None) -> list[Order]:
        stmt = select(Order).order_by(Order.created_at.desc())
        if user_id is not None:
            stmt = stmt.where(Order.user_id == user_id)
        return list(await self._session.scalars(stmt))

    # --- helpers ---------------------------------------------------------
    async def _get_owned(self, order_id: str, claims_sub: str, *, is_admin: bool) -> Order:
        order = await self._session.get(Order, order_id)
        if order is None:
            raise NotFoundError(f"Order '{order_id}' not found", details={"id": order_id})
        if not is_admin and order.user_id != claims_sub:
            raise ForbiddenError("Not the owner of this order", details={"id": order_id})
        return order
