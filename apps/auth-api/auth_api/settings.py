from __future__ import annotations

from pydantic import AliasChoices, Field

from cplatform.config import ServiceSettings, get_settings


class AuthSettings(ServiceSettings):
    service_name: str = "auth-api"
    # auth-api owns its own database. Distinct env var keeps services isolated.
    postgres_dsn: str = Field(
        default="postgresql+asyncpg://commerce:commerce@localhost:5432/auth",
        validation_alias=AliasChoices("AUTH_POSTGRES_DSN", "POSTGRES_DSN"),
    )
    db_echo: bool = False
    # Seed an initial admin on startup (local/dev convenience).
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "admin12345"


def settings() -> AuthSettings:
    return get_settings(AuthSettings)
