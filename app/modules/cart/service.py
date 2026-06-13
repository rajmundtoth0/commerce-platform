"""Cart service.

Writes (add/remove items) validate against the authoritative product table.
Building the cart *view* reads from the product and product-price projections —
this is the primary example of the public API consuming the read model. When a
projection entry is missing the line is returned unpriced and the view flags it,
rather than failing the whole request: failure modes are made visible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.cart.models import Cart, CartItem
from app.modules.cart.schemas import AddItem, CartLineView, CartView
from app.modules.pricing.projections import ProductPriceProjectionWriter
from app.modules.products.models import Product
from app.modules.products.projections import ProductProjectionWriter
from app.shared.exceptions import NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CartService:
    def __init__(
        self,
        session: AsyncSession,
        products: ProductProjectionWriter,
        prices: ProductPriceProjectionWriter,
    ) -> None:
        self._session = session
        self._products = products
        self._prices = prices

    async def _get_or_create_cart(self, user_id: str) -> Cart:
        cart = await self._session.scalar(select(Cart).where(Cart.user_id == user_id))
        if cart is None:
            cart = Cart(user_id=user_id)
            self._session.add(cart)
            await self._session.flush()
        return cart

    async def add_item(self, user_id: str, data: AddItem) -> CartView:
        product = await self._session.get(Product, data.product_id)
        if product is None:
            raise NotFoundError(
                f"Product '{data.product_id}' not found", details={"id": data.product_id}
            )
        cart = await self._get_or_create_cart(user_id)
        item = await self._session.scalar(
            select(CartItem).where(
                CartItem.cart_id == cart.id, CartItem.product_id == data.product_id
            )
        )
        if item is None:
            item = CartItem(cart_id=cart.id, product_id=data.product_id, quantity=data.quantity)
            self._session.add(item)
        else:
            item.quantity += data.quantity
        await self._session.flush()
        return await self.view(user_id)

    async def remove_item(self, user_id: str, product_id: str) -> CartView:
        cart = await self._get_or_create_cart(user_id)
        item = await self._session.scalar(
            select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
        )
        if item is None:
            raise NotFoundError(
                f"Product '{product_id}' is not in the cart", details={"id": product_id}
            )
        await self._session.delete(item)
        await self._session.flush()
        return await self.view(user_id)

    async def view(self, user_id: str) -> CartView:
        cart = await self._get_or_create_cart(user_id)
        items = list(
            await self._session.scalars(select(CartItem).where(CartItem.cart_id == cart.id))
        )

        lines: list[CartLineView] = []
        total = 0
        currency: str | None = None
        unpriced = False

        for item in items:
            product_proj = await self._products.read(item.product_id)
            price_proj = await self._prices.read(item.product_id)
            name = product_proj.name if product_proj else item.product_id

            if price_proj is None:
                unpriced = True
                lines.append(
                    CartLineView(product_id=item.product_id, name=name, quantity=item.quantity)
                )
                continue

            currency = currency or price_proj.currency
            line_amount = price_proj.amount_minor * item.quantity
            total += line_amount
            lines.append(
                CartLineView(
                    product_id=item.product_id,
                    name=name,
                    quantity=item.quantity,
                    currency=price_proj.currency,
                    unit_amount_minor=price_proj.amount_minor,
                    line_amount_minor=line_amount,
                )
            )

        return CartView(
            cart_id=cart.id,
            user_id=user_id,
            currency=currency,
            items=lines,
            total_amount_minor=total,
            has_unpriced_items=unpriced,
        )

    async def clear(self, user_id: str) -> None:
        cart = await self._get_or_create_cart(user_id)
        for item in list(
            await self._session.scalars(select(CartItem).where(CartItem.cart_id == cart.id))
        ):
            await self._session.delete(item)
        await self._session.flush()
