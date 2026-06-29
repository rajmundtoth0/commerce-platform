from __future__ import annotations

from pydantic import AliasChoices, Field

from cplatform.config import ServiceSettings, get_settings
from status_api.checks import DEFAULT_CHECKS, CheckSpec


class StatusSettings(ServiceSettings):
    service_name: str = "status-api"
    postgres_dsn: str = Field(
        default="postgresql+asyncpg://commerce:commerce@localhost:5432/status",
        validation_alias=AliasChoices("STATUS_POSTGRES_DSN", "POSTGRES_DSN"),
    )
    db_echo: bool = False

    # Single internal ops token for write endpoints (never logged/returned).
    ops_status_token: str = Field(
        default="dev-ops-token-change-me",
        validation_alias=AliasChoices("OPS_STATUS_TOKEN"),
    )

    # Health checks; override with STATUS_CHECKS (JSON array) or Helm values.
    status_checks: list[CheckSpec] = Field(default_factory=lambda: list(DEFAULT_CHECKS))
    status_refresh_interval_seconds: int = 30
    status_check_timeout_seconds: float = 2.0
    recent_incident_limit: int = 10


def settings() -> StatusSettings:
    return get_settings(StatusSettings)
