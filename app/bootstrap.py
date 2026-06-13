"""Projection wiring and rebuild registry.

Two responsibilities, kept together because they share the same per-domain
knowledge:

1. `wire_projections` subscribes every projection writer to the event bus, so a
   running app keeps Redis in sync as the write model changes.
2. `REBUILDERS` lists, per domain, how to rebuild that projection family from
   Postgres. The rebuild job (app/cli) and tests use this to recreate the entire
   read model from the source of truth.

A rebuilder is the recovery path that makes Redis safe to treat as disposable.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.metrics import PROJECTION_REBUILDS
from app.core.redis import RedisClient
from app.modules.pricing.projections import ProductPriceProjectionWriter
from app.modules.pricing.schemas import ProductPriceProjection
from app.modules.pricing.service import PricingService
from app.modules.products.projections import ProductProjectionWriter
from app.modules.products.schemas import ProductProjection
from app.modules.products.service import ProductService
from app.shared.events import EventBus

logger = get_logger(__name__)


def wire_projections(bus: EventBus, redis: RedisClient) -> None:
    """Subscribe all projection writers to the event bus."""
    from app.modules.pricing import projections as pricing_projections
    from app.modules.products import projections as product_projections

    product_projections.register(bus, ProductProjectionWriter(redis))
    pricing_projections.register(bus, ProductPriceProjectionWriter(redis))
    logger.info("projections.wired", domains=["product", "product-price"])


# --- Rebuilders -----------------------------------------------------------
RebuildFn = Callable[[AsyncSession, RedisClient], Awaitable[int]]


@dataclass(frozen=True, slots=True)
class Rebuilder:
    domain: str
    fn: RebuildFn


async def _rebuild_products(session: AsyncSession, redis: RedisClient) -> int:
    writer = ProductProjectionWriter(redis)
    await writer.clear()
    # A throwaway bus: rebuild reads straight from Postgres and writes Redis,
    # bypassing event publication entirely.
    service = ProductService(session, EventBus())
    count = 0
    async for product in service.iter_all():
        await writer.write(
            product.id,
            ProductProjection(
                id=product.id,
                sku=product.sku,
                name=product.name,
                description=product.description,
                active=product.active,
            ),
        )
        count += 1
    return count


async def _rebuild_prices(session: AsyncSession, redis: RedisClient) -> int:
    writer = ProductPriceProjectionWriter(redis)
    await writer.clear()
    service = PricingService(session, EventBus())
    count = 0
    async for price in service.iter_all():
        await writer.write(
            price.product_id,
            ProductPriceProjection(
                product_id=price.product_id,
                currency=price.currency,
                amount_minor=price.amount_minor,
            ),
        )
        count += 1
    return count


REBUILDERS: list[Rebuilder] = [
    Rebuilder(domain="product", fn=_rebuild_products),
    Rebuilder(domain="product-price", fn=_rebuild_prices),
]


async def rebuild_all(session: AsyncSession, redis: RedisClient) -> dict[str, int]:
    """Rebuild every projection family from Postgres. Returns counts per domain."""
    results: dict[str, int] = {}
    for rb in REBUILDERS:
        try:
            count = await rb.fn(session, redis)
            results[rb.domain] = count
            PROJECTION_REBUILDS.labels(domain=rb.domain, result="ok").inc()
            logger.info("projection.rebuild.done", domain=rb.domain, count=count)
        except Exception:
            PROJECTION_REBUILDS.labels(domain=rb.domain, result="error").inc()
            logger.error("projection.rebuild.failed", domain=rb.domain, exc_info=True)
            raise
    return results
