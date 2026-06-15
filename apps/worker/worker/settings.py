from __future__ import annotations

from pydantic import AliasChoices, Field

from cplatform.config import ServiceSettings, get_settings


class WorkerSettings(ServiceSettings):
    service_name: str = "worker"
    # The worker reads the OWNING services' databases to rebuild projections.
    # It is part of the platform, not a service that owns its own data.
    backoffice_postgres_dsn: str = Field(
        default="postgresql+asyncpg://commerce:commerce@localhost:5432/backoffice",
        validation_alias=AliasChoices("BACKOFFICE_POSTGRES_DSN"),
    )
    orders_postgres_dsn: str = Field(
        default="postgresql+asyncpg://commerce:commerce@localhost:5432/orders",
        validation_alias=AliasChoices("ORDERS_POSTGRES_DSN"),
    )
    metrics_port: int = 9100


def settings() -> WorkerSettings:
    return get_settings(WorkerSettings)
