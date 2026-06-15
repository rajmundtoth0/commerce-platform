"""Operational endpoints (/health, /ready, /metrics) as a reusable router.

Each service builds this router with its own readiness checks (its database, the
Valkey connection, …). Liveness is cheap; readiness probes dependencies and
returns 503 when one is down so Kubernetes stops routing to the pod.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Response

from cplatform.logging import get_logger
from cplatform.metrics import render_latest

logger = get_logger("ops")

# A readiness check returns None on success or raises on failure.
ReadinessCheck = tuple[str, Callable[[], Awaitable[None]]]


def build_ops_router(checks: list[ReadinessCheck]) -> APIRouter:
    router = APIRouter(tags=["ops"])

    @router.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/ready", include_in_schema=False)
    async def ready(response: Response) -> dict[str, object]:
        results: dict[str, str] = {}
        healthy = True
        for name, check in checks:
            try:
                await check()
                results[name] = "ok"
            except Exception as exc:  # readiness reports, never raises.
                healthy = False
                results[name] = "error"
                logger.warning("ready.check.failed", check=name, error=str(exc))
        if not healthy:
            response.status_code = 503
        return {"status": "ok" if healthy else "degraded", "checks": results}

    @router.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        payload, content_type = render_latest()
        return Response(content=payload, media_type=content_type)

    return router
