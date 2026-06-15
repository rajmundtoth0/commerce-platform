"""Async SQLAlchemy engine/session factory used by API services.

Each service owns its own database; it creates its own `Database` instance with
its own DSN and its own declarative `Base` (subclassed per service so metadata
stays isolated). The worker uses a sync engine instead (see `sync_db.py`).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def _engine_kwargs(dsn: str, echo: bool) -> dict[str, Any]:
    if dsn.startswith("sqlite"):
        return {"echo": echo}
    return {"echo": echo, "pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}


class Database:
    """Holds the async engine + sessionmaker for one service's database."""

    def __init__(self, dsn: str, *, echo: bool = False) -> None:
        self.dsn = dsn
        self.engine: AsyncEngine = create_async_engine(dsn, **_engine_kwargs(dsn, echo))
        self.sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self.engine, expire_on_commit=False, autoflush=False
        )

    async def session_dependency(self) -> AsyncGenerator[AsyncSession]:
        """FastAPI dependency: request-scoped session with commit/rollback."""
        session = self.sessionmaker()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def ping(self) -> None:
        from sqlalchemy import text

        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()
