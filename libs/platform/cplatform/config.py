"""Base settings shared by every service.

Each service subclasses `ServiceSettings`, sets its own `service_name` default and
adds service-specific fields (e.g. its own Postgres DSN). Configuration always
comes from the environment (12-factor); nothing reads `os.environ` directly.
"""

from __future__ import annotations

from functools import cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]


class ServiceSettings(BaseSettings):
    """Configuration common to all services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Identity
    service_name: str = "service"
    app_env: Environment = "local"
    log_level: str = "INFO"

    # Valkey (Redis-compatible) — projections cache + Celery broker/backend.
    # Separate logical DBs keep projection data and task queues from colliding.
    valkey_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Auth — symmetric JWT shared across services (issued by auth-api).
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 3600
    refresh_token_ttl_seconds: int = 1209600  # 14 days

    # OpenTelemetry — empty endpoint disables export but keeps instrumentation.
    otel_exporter_otlp_endpoint: str = ""
    otel_traces_sampler_arg: float = Field(default=1.0, ge=0.0, le=1.0)

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def otel_enabled(self) -> bool:
        return bool(self.otel_exporter_otlp_endpoint)


@cache
def _cached[S: ServiceSettings](cls: type[S]) -> S:
    return cls()


def get_settings[S: ServiceSettings](cls: type[S]) -> S:
    """Return a cached settings instance for the given settings subclass."""
    from typing import cast

    return cast(S, _cached(cls))
