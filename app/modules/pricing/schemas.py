"""Pricing API schemas and the product-price projection payload."""

from __future__ import annotations

from pydantic import Field

from app.shared.dto import APIModel


class PriceUpsert(APIModel):
    currency: str = Field(default="USD", min_length=3, max_length=3)
    amount_minor: int = Field(ge=0, description="Amount in integer minor units (e.g. cents).")


class PriceRead(APIModel):
    product_id: str
    currency: str
    amount_minor: int


class ProductPriceProjection(APIModel):
    """Read-model payload cached under dk:product-price:v1:{product_id}."""

    product_id: str
    currency: str
    amount_minor: int
