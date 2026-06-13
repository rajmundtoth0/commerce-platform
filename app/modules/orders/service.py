"""Orders service — checkout turns a priced cart view into an order.

Checkout reads the cart view (which is built from the read projections), refuses
to proceed if the cart is empty or has unpriced lines, snapshots the prices into
order items, then clears the cart. The price snapshot makes orders immutable
against later pricing changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.modules.cart.service import CartService
from app.modules.orders.models import Order, OrderItem
from app.shared.exceptions import ConflictError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class OrderService:
    def __init__(self, session: AsyncSession, cart: CartService) -> None:
        self._session = session
        self._cart = cart

    async def checkout(self, user_id: str) -> Order:
        view = await self._cart.view(user_id)
        if not view.items:
            raise ConflictError("Cannot check out an empty cart", details={"user_id": user_id})
        if view.has_unpriced_items:
            raise ConflictError(
                "Cart contains products without a price; cannot check out",
                details={"user_id": user_id},
            )
        assert view.currency is not None  # guaranteed when there are priced items

        order = Order(
            user_id=user_id,
            currency=view.currency,
            total_amount_minor=view.total_amount_minor,
            status="created",
        )
        for line in view.items:
            assert line.unit_amount_minor is not None
            order.items.append(
                OrderItem(
                    product_id=line.product_id,
                    product_name=line.name,
                    quantity=line.quantity,
                    unit_amount_minor=line.unit_amount_minor,
                )
            )
        self._session.add(order)
        await self._session.flush()
        await self._cart.clear(user_id)
        return order

    async def get(self, order_id: str) -> Order:
        order = await self._session.get(Order, order_id)
        if order is None:
            raise NotFoundError(f"Order '{order_id}' not found", details={"id": order_id})
        return order

    async def list_for_user(
        self, user_id: str, *, limit: int, offset: int
    ) -> tuple[list[Order], int]:
        total = (
            await self._session.scalar(
                select(func.count()).select_from(Order).where(Order.user_id == user_id)
            )
            or 0
        )
        rows = await self._session.scalars(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(rows), total
