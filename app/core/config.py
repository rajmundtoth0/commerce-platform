"""Application configuration.

All runtime configuration is sourced from environment variables (12-factor).
A single cached `Settings` instance is the one place the rest of the code reads
configuration from — no module reaches for `os.environ` directly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]


class Settings(BaseSettings):
    """Typed, validated view of the process environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core -------------------------------------------------------------
    app_env: Environment = "local"
    service_name: str = "commerce-platform"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # --- Postgres (source of truth) --------------------------------------
    # Must be an async driver DSN, e.g. postgresql+asyncpg://user:pass@host/db
    postgres_dsn: str = "postgresql+asyncpg://commerce:commerce@localhost:5432/commerce"
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # --- Redis (versioned read projections) ------------------------------
    redis_url: str = "redis://localhost:6379/0"

    # --- OpenTelemetry ----------------------------------------------------
    # Empty endpoint disables OTLP export; instrumentation still records spans
    # to a no-op processor so the app behaves identically with/without a
    # collector attached.
    otel_exporter_otlp_endpoint: str = ""
    otel_traces_sampler_arg: float = Field(default=1.0, ge=0.0, le=1.0)

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def otel_enabled(self) -> bool:
        return bool(self.otel_exporter_otlp_endpoint)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
