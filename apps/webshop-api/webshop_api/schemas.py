from __future__ import annotations

from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    id: str
    sku: str
    name: str
    description: str
    featured: bool
    currency: str | None = None
    amount_minor: int | None = None


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int
    limit: int
    offset: int


class AddItemIn(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=999)


class CartLineOut(BaseModel):
    product_id: str
    name: str
    quantity: int
    currency: str | None = None
    unit_amount_minor: int | None = None
    line_amount_minor: int | None = None


class CartView(BaseModel):
    cart_id: str
    currency: str | None
    items: list[CartLineOut]
    total_amount_minor: int
    has_unpriced_items: bool


class CheckoutIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class OrderItemOut(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_amount_minor: int


class OrderOut(BaseModel):
    id: str
    status: str
    currency: str
    total_amount_minor: int
    items: list[OrderItemOut]
