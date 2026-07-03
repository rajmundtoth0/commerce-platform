"""Shared test setup for all services.

Tests are hermetic: each service's Postgres is a temp-file SQLite database and
Valkey is fakeredis (async + sync). Environment is configured before any service
module is imported, since services build their Database/clients at import time.
"""

from __future__ import annotations

import os
import tempfile

# --- Configure environment BEFORE importing any service module. -----------
_DBS = {
    name: tempfile.mkstemp(suffix=f"-{name}.db")[1]
    for name in ("auth", "orders", "backoffice", "status")
}
OPS_STATUS_TOKEN = "test-ops-token"
os.environ.update(
    APP_ENV="test",
    LOG_LEVEL="WARNING",
    JWT_SECRET="test-secret-test-secret-test-secret-0123456789",
    AUTH_POSTGRES_DSN=f"sqlite+aiosqlite:///{_DBS['auth']}",
    ORDERS_POSTGRES_DSN=f"sqlite+aiosqlite:///{_DBS['orders']}",
    BACKOFFICE_POSTGRES_DSN=f"sqlite+aiosqlite:///{_DBS['backoffice']}",
    STATUS_POSTGRES_DSN=f"sqlite+aiosqlite:///{_DBS['status']}",
    OPS_STATUS_TOKEN=OPS_STATUS_TOKEN,
    VALKEY_URL="redis://localhost:6380/0",
    CELERY_BROKER_URL="memory://",
    CELERY_RESULT_BACKEND="cache+memory://",
    OTEL_EXPORTER_OTLP_ENDPOINT="",
)

import fakeredis  # noqa: E402
import fakeredis.aioredis  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from cplatform import valkey as valkey_module  # noqa: E402

VALKEY_URL = "redis://localhost:6380/0"

# A single shared fake Valkey backs both async and sync views in tests.
_fake_server = fakeredis.FakeServer()


@pytest_asyncio.fixture(autouse=True)
async def _valkey() -> None:
    """Fresh fake Valkey (async + sync) per test, sharing one keyspace."""
    async_client = fakeredis.aioredis.FakeRedis(server=_fake_server, decode_responses=True)
    sync_client = fakeredis.FakeRedis(server=_fake_server, decode_responses=True)
    valkey_module.set_async_valkey(VALKEY_URL, async_client)
    valkey_module.set_sync_valkey(VALKEY_URL, sync_client)
    sync_client.flushall()
    yield
    await async_client.flushall()


@pytest_asyncio.fixture
async def auth_client() -> AsyncClient:
    from auth_api.deps import database
    from auth_api.main import app
    from auth_api.models import Base

    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://auth") as client:
        # trigger lifespan (seed admin) manually for ASGITransport
        async with app.router.lifespan_context(app):
            yield client
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
