"""Synchronous SQLAlchemy session factory for the Celery worker.

The worker reads authoritative data from owning services' databases to rebuild
projections. Celery tasks are synchronous, so we use a sync engine (psycopg)
rather than the async engine the API services use.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def to_sync_dsn(dsn: str) -> str:
    """Convert an async DSN to its sync (psycopg) equivalent."""
    return dsn.replace("+asyncpg", "+psycopg").replace("sqlite+aiosqlite", "sqlite")


class SyncDatabase:
    def __init__(self, dsn: str, *, echo: bool = False) -> None:
        self.engine: Engine = create_engine(to_sync_dsn(dsn), echo=echo, pool_pre_ping=True)
        self.sessionmaker = sessionmaker(bind=self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        s = self.sessionmaker()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()
