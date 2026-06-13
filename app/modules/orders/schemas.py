"""Orders API schemas."""

from __future__ import annotations

from app.shared.dto import APIModel


class OrderItemRead(APIModel):
    product_id: str
    product_name: str
    quantity: int
    unit_amount_minor: int


class OrderRead(APIModel):
    id: str
    user_id: str
    status: str
    currency: str
    total_amount_minor: int
    items: list[OrderItemRead]
