"""Products service — the write-model use cases.

The service owns business rules and persistence for the authoritative model. It
knows nothing about HTTP. After each mutation it publishes a domain event so the
projection writer can update Redis; the event carries a full snapshot so the
handler never re-reads the database.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.modules.products.models import Product
from app.modules.products.schemas import ProductCreate, ProductUpdate
from app.shared.events import EventBus, ProductDeleted, ProductUpserted
from app.shared.exceptions import ConflictError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ProductService:
    def __init__(self, session: AsyncSession, bus: EventBus) -> None:
        self._session = session
        self._bus = bus

    def _snapshot_event(self, product: Product) -> ProductUpserted:
        return ProductUpserted(
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            description=product.description,
            active=product.active,
        )

    async def create(self, data: ProductCreate) -> Product:
        product = Product(
            sku=data.sku,
            name=data.name,
            description=data.description,
            active=data.active,
        )
        self._session.add(product)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                f"Product with sku '{data.sku}' already exists", details={"sku": data.sku}
            ) from exc
        await self._bus.publish(self._snapshot_event(product))
        return product

    async def get(self, product_id: str) -> Product:
        product = await self._session.get(Product, product_id)
        if product is None:
            raise NotFoundError(f"Product '{product_id}' not found", details={"id": product_id})
        return product

    async def list(self, *, limit: int, offset: int) -> tuple[list[Product], int]:
        total = await self._session.scalar(select(func.count()).select_from(Product)) or 0
        rows = await self._session.scalars(
            select(Product).order_by(Product.created_at.desc()).limit(limit).offset(offset)
        )
        return list(rows), total

    async def update(self, product_id: str, data: ProductUpdate) -> Product:
        product = await self.get(product_id)
        patch = data.model_dump(exclude_unset=True)
        for field, value in patch.items():
            setattr(product, field, value)
        await self._session.flush()
        await self._bus.publish(self._snapshot_event(product))
        return product

    async def delete(self, product_id: str) -> None:
        product = await self.get(product_id)
        await self._session.delete(product)
        await self._session.flush()
        await self._bus.publish(ProductDeleted(product_id=product_id))

    async def iter_all(self) -> AsyncIterator[Product]:
        """Stream every product — used by the projection rebuild job."""
        result = await self._session.stream_scalars(select(Product))
        async for product in result:
            yield product
