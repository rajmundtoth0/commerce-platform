"""Pricing service — set/read/clear the current price for a product."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.pricing.models import ProductPrice
from app.modules.pricing.schemas import PriceUpsert
from app.modules.products.models import Product
from app.shared.events import EventBus, PriceDeleted, PriceUpserted
from app.shared.exceptions import NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PricingService:
    def __init__(self, session: AsyncSession, bus: EventBus) -> None:
        self._session = session
        self._bus = bus

    async def _require_product(self, product_id: str) -> None:
        exists = await self._session.get(Product, product_id)
        if exists is None:
            raise NotFoundError(f"Product '{product_id}' not found", details={"id": product_id})

    async def get(self, product_id: str) -> ProductPrice:
        price = await self._session.get(ProductPrice, product_id)
        if price is None:
            raise NotFoundError(
                f"No price set for product '{product_id}'", details={"id": product_id}
            )
        return price

    async def upsert(self, product_id: str, data: PriceUpsert) -> ProductPrice:
        await self._require_product(product_id)
        price = await self._session.get(ProductPrice, product_id)
        if price is None:
            price = ProductPrice(
                product_id=product_id, currency=data.currency, amount_minor=data.amount_minor
            )
            self._session.add(price)
        else:
            price.currency = data.currency
            price.amount_minor = data.amount_minor
        await self._session.flush()
        await self._bus.publish(
            PriceUpserted(
                product_id=product_id, currency=price.currency, amount_minor=price.amount_minor
            )
        )
        return price

    async def delete(self, product_id: str) -> None:
        price = await self.get(product_id)
        await self._session.delete(price)
        await self._session.flush()
        await self._bus.publish(PriceDeleted(product_id=product_id))

    async def iter_all(self) -> AsyncIterator[ProductPrice]:
        result = await self._session.stream_scalars(select(ProductPrice))
        async for price in result:
            yield price
