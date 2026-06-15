"""Catalog reads — served entirely from the Valkey read projections.

webshop-api never touches a product database; it depends only on the projection
*contracts* (cplatform.contracts). Listing scans the product key space and joins
the price projection per item. (For a larger catalog you would maintain a
secondary index set instead of scanning; documented as a deliberate trade-off.)
"""

from __future__ import annotations

from cplatform.contracts import (
    PRODUCT_PRICE_SPEC,
    PRODUCT_SPEC,
    ProductPriceProjection,
    ProductProjection,
)
from cplatform.projections import AsyncProjectionReader
from cplatform.valkey import AsyncValkey
from webshop_api.schemas import ProductOut


class CatalogReader:
    def __init__(self, client: AsyncValkey, *, service: str) -> None:
        self._client = client
        self._products = AsyncProjectionReader(PRODUCT_SPEC, client, service=service)
        self._prices = AsyncProjectionReader(PRODUCT_PRICE_SPEC, client, service=service)

    async def _all_product_ids(self) -> list[str]:
        prefix = f"{PRODUCT_SPEC.key('')}"  # dk:product:v1:
        ids: list[str] = []
        async for key in self._client.scan_iter(match=PRODUCT_SPEC.scan_pattern()):
            ids.append(key[len(prefix) :])
        ids.sort()
        return ids

    def _merge(
        self, product: ProductProjection, price: ProductPriceProjection | None
    ) -> ProductOut:
        return ProductOut(
            id=product.id,
            sku=product.sku,
            name=product.name,
            description=product.description,
            featured=product.featured,
            currency=price.currency if price else None,
            amount_minor=price.amount_minor if price else None,
        )

    async def get(self, product_id: str) -> ProductOut | None:
        product = await self._products.read(product_id)
        if product is None or not product.active:
            return None
        price = await self._prices.read(product_id)
        return self._merge(product, price)

    async def list_page(self, *, limit: int, offset: int) -> tuple[list[ProductOut], int]:
        out: list[ProductOut] = []
        for product_id in await self._all_product_ids():
            product = await self._products.read(product_id)
            if product is None or not product.active:
                continue
            price = await self._prices.read(product_id)
            out.append(self._merge(product, price))
        total = len(out)
        return out[offset : offset + limit], total

    async def featured(self) -> list[ProductOut]:
        items, _ = await self.list_page(limit=1000, offset=0)
        return [p for p in items if p.featured]
