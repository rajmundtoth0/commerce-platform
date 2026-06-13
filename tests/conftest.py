"""Test fixtures.

Tests run fully self-contained — no Postgres or Redis required:
  * Postgres  -> a temp-file SQLite database (async, via aiosqlite)
  * Redis     -> fakeredis' async client

This keeps `pytest` (and CI) hermetic while exercising the real services,
projection writers, routers, and event wiring.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator

# Configure the environment BEFORE importing any app module that reads settings.
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)
os.environ.update(
    APP_ENV="test",
    LOG_LEVEL="WARNING",
    POSTGRES_DSN=f"sqlite+aiosqlite:///{_DB_PATH}",
    REDIS_URL="redis://localhost:6379/0",  # not used; fakeredis is injected
    OTEL_EXPORTER_OTLP_ENDPOINT="",
)

import fakeredis.aioredis  # noqa: E402
import pytest_asyncio  # noqa: E402
from app.bootstrap import wire_projections  # noqa: E402
from app.core import redis as redis_module  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import dispose_engine, get_engine, get_sessionmaker  # noqa: E402
from app.models import Base  # noqa: E402
from app.shared.events import get_event_bus, reset_event_bus  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

get_settings.cache_clear()


@pytest_asyncio.fixture(autouse=True)
async def _schema() -> AsyncIterator[None]:
    """Fresh schema + fresh fake Redis + fresh event wiring per test."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_module.set_redis(fake)

    reset_event_bus()
    wire_projections(get_event_bus(), fake)

    yield

    await fake.flushall()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTP client bound to the ASGI app (no network)."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """A standalone session for service/projection unit tests.

    Tests that need data persisted call ``await session.commit()`` themselves;
    teardown only closes the session (the context manager rolls back any
    in-flight transaction), so an expected IntegrityError mid-test doesn't turn
    into a teardown error.
    """
    async with get_sessionmaker()() as s:
        yield s


@pytest_asyncio.fixture
async def redis() -> fakeredis.aioredis.FakeRedis:
    return redis_module.get_redis()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_engine() -> AsyncIterator[None]:
    yield
    await dispose_engine()
    try:
        os.unlink(_DB_PATH)
    except OSError:
        pass
