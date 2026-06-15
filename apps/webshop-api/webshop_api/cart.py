"""Customer-facing cart, stored in Valkey.

The cart is mutable session state (NOT a `dk:` read projection): it lives at
`cart:v1:{cart_id}` as a small JSON document. The cart *view* (names, prices,
totals) is assembled by joining the product and product-price projections, so a
product without a price projection yields an "unpriced" line and the view flags
it rather than failing.
"""

from __future__ import annotations

import json

from cplatform.contracts import PRODUCT_PRICE_SPEC, PRODUCT_SPEC
from cplatform.errors import NotFoundError
from cplatform.projections import AsyncProjectionReader
from cplatform.valkey import AsyncValkey
from webshop_api.schemas import CartLineOut, CartView

CART_KEY_VERSION = 1


def _cart_key(cart_id: str) -> str:
    return f"cart:v{CART_KEY_VERSION}:{cart_id}"


class CartService:
    def __init__(self, client: AsyncValkey, *, service: str, ttl_seconds: int) -> None:
        self._client = client
        self._ttl = ttl_seconds
        self._products = AsyncProjectionReader(PRODUCT_SPEC, client, service=service)
        self._prices = AsyncProjectionReader(PRODUCT_PRICE_SPEC, client, service=service)

    async def _load(self, cart_id: str) -> dict[str, int]:
        raw = await self._client.get(_cart_key(cart_id))
        if raw is None:
            return {}
        data = json.loads(raw)
        return {str(k): int(v) for k, v in data.get("items", {}).items()}

    async def _save(self, cart_id: str, items: dict[str, int]) -> None:
        await self._client.set(_cart_key(cart_id), json.dumps({"items": items}), ex=self._ttl)

    async def add_item(self, cart_id: str, product_id: str, quantity: int) -> CartView:
        if await self._products.read(product_id) is None:
            raise NotFoundError(f"Product '{product_id}' not found", details={"id": product_id})
        items = await self._load(cart_id)
        items[product_id] = items.get(product_id, 0) + quantity
        await self._save(cart_id, items)
        return await self.view(cart_id)

    async def remove_item(self, cart_id: str, product_id: str) -> CartView:
        items = await self._load(cart_id)
        if product_id not in items:
            raise NotFoundError(f"Product '{product_id}' not in cart", details={"id": product_id})
        del items[product_id]
        await self._save(cart_id, items)
        return await self.view(cart_id)

    async def clear(self, cart_id: str) -> None:
        await self._client.delete(_cart_key(cart_id))

    async def view(self, cart_id: str) -> CartView:
        items = await self._load(cart_id)
        lines: list[CartLineOut] = []
        total = 0
        currency: str | None = None
        unpriced = False
        for product_id, qty in items.items():
            product = await self._products.read(product_id)
            price = await self._prices.read(product_id)
            name = product.name if product else product_id
            if price is None:
                unpriced = True
                lines.append(CartLineOut(product_id=product_id, name=name, quantity=qty))
                continue
            currency = currency or price.currency
            line_amount = price.amount_minor * qty
            total += line_amount
            lines.append(
                CartLineOut(
                    product_id=product_id,
                    name=name,
                    quantity=qty,
                    currency=price.currency,
                    unit_amount_minor=price.amount_minor,
                    line_amount_minor=line_amount,
                )
            )
        return CartView(
            cart_id=cart_id,
            currency=currency,
            items=lines,
            total_amount_minor=total,
            has_unpriced_items=unpriced,
        )
