from __future__ import annotations

from cplatform.service import create_service_app
from cplatform.valkey import close_async_valkey, get_async_valkey
from webshop_api.deps import _orders_gateway
from webshop_api.router import cart_router, catalog_router, checkout_router
from webshop_api.settings import settings

_settings = settings()


async def _valkey_ping() -> None:
    await get_async_valkey(_settings.valkey_url).ping()


async def _shutdown() -> None:
    await _orders_gateway.aclose()
    await close_async_valkey()


app = create_service_app(
    settings=_settings,
    title="webshop-api",
    routers=[catalog_router, cart_router, checkout_router],
    readiness_checks=[("valkey", _valkey_ping)],
    on_shutdown=_shutdown,
)
