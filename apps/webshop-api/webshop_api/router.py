from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from cplatform.errors import ConflictError
from webshop_api.deps import CartDep, CatalogDep, OrdersDep
from webshop_api.schemas import (
    AddItemIn,
    CartView,
    CheckoutIn,
    OrderOut,
    ProductOut,
    ProductPage,
)

catalog_router = APIRouter(prefix="/catalog", tags=["catalog"])
cart_router = APIRouter(prefix="/cart", tags=["cart"])
checkout_router = APIRouter(tags=["checkout"])


@catalog_router.get("/featured", response_model=list[ProductOut])
async def featured(catalog: CatalogDep) -> list[ProductOut]:
    return await catalog.featured()


@catalog_router.get("/products", response_model=ProductPage)
async def list_products(
    catalog: CatalogDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductPage:
    items, total = await catalog.list_page(limit=limit, offset=offset)
    return ProductPage(items=items, total=total, limit=limit, offset=offset)


@catalog_router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: str, catalog: CatalogDep) -> ProductOut:
    from cplatform.errors import NotFoundError

    product = await catalog.get(product_id)
    if product is None:
        raise NotFoundError(f"Product '{product_id}' not found", details={"id": product_id})
    return product


@cart_router.get("/{cart_id}", response_model=CartView)
async def get_cart(cart_id: str, cart: CartDep) -> CartView:
    return await cart.view(cart_id)


@cart_router.post("/{cart_id}/items", response_model=CartView, status_code=201)
async def add_item(cart_id: str, data: AddItemIn, cart: CartDep) -> CartView:
    return await cart.add_item(cart_id, data.product_id, data.quantity)


@cart_router.delete("/{cart_id}/items/{product_id}", response_model=CartView)
async def remove_item(cart_id: str, product_id: str, cart: CartDep) -> CartView:
    return await cart.remove_item(cart_id, product_id)


@checkout_router.post("/checkout/{cart_id}", response_model=OrderOut, status_code=201)
async def checkout(cart_id: str, data: CheckoutIn, cart: CartDep, orders: OrdersDep) -> OrderOut:
    view = await cart.view(cart_id)
    if not view.items:
        raise ConflictError("Cannot check out an empty cart")
    if view.has_unpriced_items or view.currency is None:
        raise ConflictError("Cart has unpriced items; cannot check out")
    items: list[dict[str, object]] = [
        {
            "product_id": line.product_id,
            "product_name": line.name,
            "quantity": line.quantity,
            "unit_amount_minor": line.unit_amount_minor,
        }
        for line in view.items
    ]
    order = await orders.create_order(email=data.email, currency=view.currency, items=items)
    await cart.clear(cart_id)
    return order


@checkout_router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: str,
    orders: OrdersDep,
    email: Annotated[str, Query(min_length=3)],
) -> OrderOut:
    # Customer order status lookup; re-derives the guest token from the email.
    return await orders.get_order(email=email, order_id=order_id)
