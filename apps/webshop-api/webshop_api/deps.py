from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from cplatform.valkey import get_async_valkey
from webshop_api.cart import CartService
from webshop_api.catalog import CatalogReader
from webshop_api.orders_gateway import OrdersGateway
from webshop_api.settings import settings

_settings = settings()
_orders_gateway = OrdersGateway(_settings)


def get_catalog() -> CatalogReader:
    return CatalogReader(get_async_valkey(_settings.valkey_url), service=_settings.service_name)


def get_cart() -> CartService:
    return CartService(
        get_async_valkey(_settings.valkey_url),
        service=_settings.service_name,
        ttl_seconds=_settings.cart_ttl_seconds,
    )


def get_orders_gateway() -> OrdersGateway:
    # Overridable in tests via app.dependency_overrides.
    return _orders_gateway


CatalogDep = Annotated[CatalogReader, Depends(get_catalog)]
CartDep = Annotated[CartService, Depends(get_cart)]
OrdersDep = Annotated[OrdersGateway, Depends(get_orders_gateway)]
