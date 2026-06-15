from __future__ import annotations

from pydantic import AliasChoices, Field

from cplatform.config import ServiceSettings, get_settings


class OrdersSettings(ServiceSettings):
    service_name: str = "orders-api"
    # orders-api owns its own database. Distinct env var keeps services isolated.
    postgres_dsn: str = Field(
        default="postgresql+asyncpg://commerce:commerce@localhost:5432/orders",
        validation_alias=AliasChoices("ORDERS_POSTGRES_DSN", "POSTGRES_DSN"),
    )
    db_echo: bool = False


def settings() -> OrdersSettings:
    return get_settings(OrdersSettings)
