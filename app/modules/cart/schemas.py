"""Cart API schemas. The cart view is assembled from read projections."""

from __future__ import annotations

from pydantic import Field

from app.shared.dto import APIModel


class AddItem(APIModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=999)


class CartLineView(APIModel):
    product_id: str
    name: str
    quantity: int
    # Price fields are None when the product-price projection has no entry yet.
    currency: str | None = None
    unit_amount_minor: int | None = None
    line_amount_minor: int | None = None


class CartView(APIModel):
    cart_id: str
    user_id: str
    currency: str | None
    items: list[CartLineView]
    total_amount_minor: int
    # True when any line is missing pricing data (read-model not yet populated).
    has_unpriced_items: bool
