"""Async SQLAlchemy 2.x engine, session factory, and declarative base.

Postgres is the authoritative store. We use the async engine throughout; the
FastAPI dependency `get_session` yields a session scoped to a single request and
commits/rolls back at the boundary.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import Settings, get_settings

# Explicit, stable constraint naming so Alembic autogenerate produces
# deterministic migration names across databases.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by all module models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """created_at / updated_at columns, managed by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def _engine_kwargs(settings: Settings) -> dict[str, Any]:
    # SQLite (used in tests) does not accept pool sizing arguments.
    if settings.postgres_dsn.startswith("sqlite"):
        return {"echo": settings.db_echo}
    return {
        "echo": settings.db_echo,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_pre_ping": True,
    }


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the lazily-created process-wide async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.postgres_dsn, **_engine_kwargs(settings))
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, autoflush=False
        )
    return _sessionmaker


async def get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency: a request-scoped session with commit/rollback.

    The session commits on success and rolls back on any exception, so handlers
    and services never have to manage the transaction boundary themselves.
    """
    session = get_sessionmaker()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Dispose the engine on shutdown. Resets module state for clean restarts."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
