"""Projection rebuild builders (worker side, SYNC SQLAlchemy).

The Celery worker imports these to (re)build product/price projections from
backoffice-api's authoritative database. They return the shared contract models
from `cplatform.contracts` — the only shape consumers may depend on. Sync only:
Celery tasks run synchronously.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from sqlalchemy import select

from backoffice_api.models import Product, ProductPrice
from cplatform.contracts import ProductPriceProjection, ProductProjection

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def build_product(session: Session, product_id: str) -> ProductProjection | None:
    product = session.get(Product, product_id)
    if product is None:
        return None
    return ProductProjection(
        id=product.id,
        sku=product.sku,
        name=product.name,
        description=product.description,
        active=product.active,
        featured=product.featured,
    )


def build_price(session: Session, product_id: str) -> ProductPriceProjection | None:
    price = session.get(ProductPrice, product_id)
    if price is None:
        return None
    return ProductPriceProjection(
        product_id=price.product_id,
        currency=price.currency,
        amount_minor=price.amount_minor,
    )


def all_products(session: Session) -> Iterator[tuple[str, ProductProjection]]:
    for product in session.scalars(select(Product)):
        yield (
            product.id,
            ProductProjection(
                id=product.id,
                sku=product.sku,
                name=product.name,
                description=product.description,
                active=product.active,
                featured=product.featured,
            ),
        )


def all_prices(session: Session) -> Iterator[tuple[str, ProductPriceProjection]]:
    for price in session.scalars(select(ProductPrice)):
        yield (
            price.product_id,
            ProductPriceProjection(
                product_id=price.product_id,
                currency=price.currency,
                amount_minor=price.amount_minor,
            ),
        )
