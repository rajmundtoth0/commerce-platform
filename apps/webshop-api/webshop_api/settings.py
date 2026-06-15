from __future__ import annotations

from cplatform.config import ServiceSettings, get_settings


class WebshopSettings(ServiceSettings):
    service_name: str = "webshop-api"
    # webshop-api owns NO database — it reads projections from Valkey and calls
    # orders-api over HTTP. This is the BFF boundary.
    orders_api_url: str = "http://localhost:8003"
    cart_ttl_seconds: int = 604800  # 7 days


def settings() -> WebshopSettings:
    return get_settings(WebshopSettings)
