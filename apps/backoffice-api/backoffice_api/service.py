from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backoffice_api.models import Product, ProductPrice
from backoffice_api.schemas import PriceUpsert, ProductCreate, ProductUpdate
from cplatform.errors import ConflictError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CatalogService:
    """Authoritative product & price operations (source of truth)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- products --------------------------------------------------------
    async def create_product(self, data: ProductCreate) -> Product:
        product = Product(
            sku=data.sku,
            name=data.name,
            description=data.description,
            active=data.active,
            featured=data.featured,
        )
        self._session.add(product)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                f"SKU '{data.sku}' already exists", details={"sku": data.sku}
            ) from exc
        return product

    async def get_product(self, product_id: str) -> Product:
        product = await self._session.get(Product, product_id)
        if product is None:
            raise NotFoundError(f"Product '{product_id}' not found", details={"id": product_id})
        return product

    async def list_products(self, *, limit: int, offset: int) -> tuple[list[Product], int]:
        total = await self._session.scalar(select(func.count()).select_from(Product)) or 0
        items = list(
            await self._session.scalars(
                select(Product).order_by(Product.created_at.desc()).limit(limit).offset(offset)
            )
        )
        return items, total

    async def update_product(self, product_id: str, data: ProductUpdate) -> Product:
        product = await self.get_product(product_id)
        fields = data.model_dump(exclude_unset=True)
        for key, value in fields.items():
            setattr(product, key, value)
        await self._session.flush()
        return product

    async def delete_product(self, product_id: str) -> None:
        product = await self.get_product(product_id)
        await self._session.delete(product)
        await self._session.flush()

    # --- prices ----------------------------------------------------------
    async def get_price(self, product_id: str) -> ProductPrice:
        price = await self._session.get(ProductPrice, product_id)
        if price is None:
            raise NotFoundError(
                f"Price for product '{product_id}' not found", details={"id": product_id}
            )
        return price

    async def upsert_price(self, product_id: str, data: PriceUpsert) -> ProductPrice:
        # Ensure the product exists (404 otherwise) before touching its price.
        await self.get_product(product_id)
        price = await self._session.get(ProductPrice, product_id)
        if price is None:
            price = ProductPrice(
                product_id=product_id,
                currency=data.currency,
                amount_minor=data.amount_minor,
            )
            self._session.add(price)
        else:
            price.currency = data.currency
            price.amount_minor = data.amount_minor
        await self._session.flush()
        return price

    async def delete_price(self, product_id: str) -> None:
        price = await self.get_price(product_id)
        await self._session.delete(price)
        await self._session.flush()
