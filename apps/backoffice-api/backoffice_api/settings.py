from __future__ import annotations

from pydantic import AliasChoices, Field

from cplatform.config import ServiceSettings, get_settings


class BackofficeSettings(ServiceSettings):
    service_name: str = "backoffice-api"
    # backoffice-api owns its own database. Distinct env var keeps services isolated.
    postgres_dsn: str = Field(
        default="postgresql+asyncpg://commerce:commerce@localhost:5432/backoffice",
        validation_alias=AliasChoices("BACKOFFICE_POSTGRES_DSN", "POSTGRES_DSN"),
    )
    db_echo: bool = False
    # Seed admin creds — also accepted by the SQLAdmin UI login (local/dev convenience).
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "admin12345"


def settings() -> BackofficeSettings:
    return get_settings(BackofficeSettings)
