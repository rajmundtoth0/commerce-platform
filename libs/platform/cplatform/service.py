"""FastAPI service app factory.

Builds a service's FastAPI app with the standard cross-cutting wiring in one
place: logging, middleware (request context + metrics), error handlers,
telemetry, and the ops router (/health, /ready, /metrics). Each service supplies
its own routers, readiness checks, and an optional lifespan callback.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI

from cplatform.config import ServiceSettings
from cplatform.errors import install_error_handlers
from cplatform.logging import configure_logging, get_logger
from cplatform.middleware import MetricsMiddleware, RequestContextMiddleware
from cplatform.ops import ReadinessCheck, build_ops_router
from cplatform.telemetry import setup_fastapi_telemetry

LifespanHook = Callable[[], Awaitable[None]]


def create_service_app(
    *,
    settings: ServiceSettings,
    title: str,
    routers: list[APIRouter],
    readiness_checks: list[ReadinessCheck] | None = None,
    engine: Any | None = None,
    on_startup: LifespanHook | None = None,
    on_shutdown: LifespanHook | None = None,
) -> FastAPI:
    configure_logging(level=settings.log_level, service_name=settings.service_name)
    logger = get_logger(settings.service_name)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info("service.startup", env=settings.app_env)
        if on_startup is not None:
            await on_startup()
        yield
        if on_shutdown is not None:
            await on_shutdown()
        logger.info("service.shutdown")

    app = FastAPI(title=title, version="0.2.0", lifespan=lifespan)
    app.add_middleware(MetricsMiddleware, service_name=settings.service_name)
    app.add_middleware(RequestContextMiddleware, service_name=settings.service_name)
    install_error_handlers(app)

    app.include_router(build_ops_router(readiness_checks or []))
    for router in routers:
        app.include_router(router)

    setup_fastapi_telemetry(
        app,
        service_name=settings.service_name,
        endpoint=settings.otel_exporter_otlp_endpoint,
        sampler_arg=settings.otel_traces_sampler_arg,
        engine=engine,
    )
    return app
