"""Cross-service projection contracts.

These payload models + specs are the *only* thing API consumers may depend on
for read data — never another service's database schema. The worker produces
them; webshop-api consumes them. Changing a payload shape requires bumping the
spec's `schema_version`; changing a key layout requires bumping `key_version`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from cplatform.projections import ProjectionSpec


class ProductProjection(BaseModel):
    id: str
    sku: str
    name: str
    description: str
    active: bool
    featured: bool  # drives the webshop-ui featured slider


class ProductPriceProjection(BaseModel):
    product_id: str
    currency: str
    amount_minor: int


class OrderSummaryProjection(BaseModel):
    order_id: str
    user_id: str
    status: str
    currency: str
    total_amount_minor: int
    item_count: int


PRODUCT_SPEC: ProjectionSpec[ProductProjection] = ProjectionSpec(
    name="product", key_version=1, schema_version=1, model=ProductProjection
)
PRODUCT_PRICE_SPEC: ProjectionSpec[ProductPriceProjection] = ProjectionSpec(
    name="product-price", key_version=1, schema_version=1, model=ProductPriceProjection
)
ORDER_SUMMARY_SPEC: ProjectionSpec[OrderSummaryProjection] = ProjectionSpec(
    name="order-summary", key_version=1, schema_version=1, model=OrderSummaryProjection
)

ALL_SPECS: list[ProjectionSpec[Any]] = [PRODUCT_SPEC, PRODUCT_PRICE_SPEC, ORDER_SUMMARY_SPEC]
