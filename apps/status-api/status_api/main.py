from __future__ import annotations

import asyncio

from cplatform.logging import get_logger
from cplatform.service import create_service_app
from status_api.deps import database
from status_api.health import HealthCollector
from status_api.router import page_router, status_router
from status_api.settings import settings

_settings = settings()
logger = get_logger(_settings.service_name)
_collector = HealthCollector(
    database, _settings.status_checks, timeout=_settings.status_check_timeout_seconds
)
_refresh_task: asyncio.Task[None] | None = None


async def _refresh_loop() -> None:
    while True:
        await asyncio.sleep(_settings.status_refresh_interval_seconds)
        try:
            await _collector.refresh()
        except Exception:  # health refresh must never crash the service
            logger.warning("status.health.refresh.failed", exc_info=True)


async def _on_startup() -> None:
    global _refresh_task
    try:
        await _collector.seed()
    except Exception as exc:  # tables may not exist yet (migration runs separately)
        logger.warning("status.seed.failed", error=str(exc))
    if not _settings.is_test:
        try:
            await _collector.refresh()
        except Exception:
            logger.warning("status.health.refresh.failed", exc_info=True)
        _refresh_task = asyncio.create_task(_refresh_loop())


async def _on_shutdown() -> None:
    if _refresh_task is not None:
        _refresh_task.cancel()
    await database.dispose()


app = create_service_app(
    settings=_settings,
    title="status-api",
    routers=[status_router, page_router],
    readiness_checks=[("postgres", database.ping)],
    engine=database.engine,
    on_startup=_on_startup,
    on_shutdown=_on_shutdown,
)
