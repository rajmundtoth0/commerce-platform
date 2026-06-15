from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from sqlalchemy import select

from cplatform.contracts import OrderSummaryProjection
from orders_api.models import Order

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _to_projection(order: Order) -> OrderSummaryProjection:
    return OrderSummaryProjection(
        order_id=order.id,
        user_id=order.user_id,
        status=order.status,
        currency=order.currency,
        total_amount_minor=order.total_amount_minor,
        item_count=sum(item.quantity for item in order.items),
    )


def build_order_summary(session: Session, order_id: str) -> OrderSummaryProjection | None:
    order = session.get(Order, order_id)
    if order is None:
        return None
    return _to_projection(order)


def all_order_summaries(session: Session) -> Iterator[tuple[str, OrderSummaryProjection]]:
    for order in session.scalars(select(Order).order_by(Order.created_at.desc())):
        yield order.id, _to_projection(order)
