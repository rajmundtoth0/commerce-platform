"""Operational CLI (`commerce ...`).

The headline command is `rebuild`, the full projection rebuild job: it rewrites
every Redis projection from Postgres. Run it after a schema/key-version bump, a
Redis flush, or whenever the read model has drifted. It is safe to run anytime
because Postgres is the source of truth.
"""

from __future__ import annotations

import asyncio
import json

import typer

from app.bootstrap import REBUILDERS, rebuild_all
from app.core.database import dispose_engine, get_sessionmaker
from app.core.logging import configure_logging, get_logger
from app.core.redis import close_redis, get_redis

app = typer.Typer(help="commerce-platform operational CLI", no_args_is_help=True)
logger = get_logger("cli")


async def _run_rebuild() -> dict[str, int]:
    redis = get_redis()
    async with get_sessionmaker()() as session:
        results = await rebuild_all(session, redis)
    await close_redis()
    await dispose_engine()
    return results


@app.command()
def rebuild() -> None:
    """Rebuild all Redis projections from Postgres (full read-model rewrite)."""
    configure_logging()
    results = asyncio.run(_run_rebuild())
    typer.echo(json.dumps({"rebuilt": results}, indent=2))


@app.command("list-projections")
def list_projections() -> None:
    """List the registered projection domains and their rebuilders."""
    for rb in REBUILDERS:
        typer.echo(rb.domain)


if __name__ == "__main__":
    app()
