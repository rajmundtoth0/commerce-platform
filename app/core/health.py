"""Operational endpoints: /health, /ready, /metrics.

- /health  — liveness. Cheap; returns 200 if the process is up.
- /ready   — readiness. Probes Postgres and Redis; 503 if a dependency is down,
             so Kubernetes stops routing traffic to a pod that can't serve.
- /metrics — Prometheus exposition format.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.core.database import get_sessionmaker
from app.core.logging import get_logger
from app.core.metrics import render_latest
from app.core.redis import get_redis

logger = get_logger(__name__)

router = APIRouter(tags=["ops"])


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", include_in_schema=False)
async def ready(response: Response) -> dict[str, object]:
    checks: dict[str, str] = {}
    healthy = True

    try:
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:  # readiness must report, not raise.
        healthy = False
        checks["postgres"] = "error"
        logger.warning("ready.postgres.failed", error=str(exc))

    try:
        await get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # readiness must report, not raise.
        healthy = False
        checks["redis"] = "error"
        logger.warning("ready.redis.failed", error=str(exc))

    if not healthy:
        response.status_code = 503
    return {"status": "ok" if healthy else "degraded", "checks": checks}


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    payload, content_type = render_latest()
    return Response(content=payload, media_type=content_type)
