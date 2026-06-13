"""FastAPI application factory and wiring.

Composition root: configure logging, build the app, install middleware and
exception handlers, mount module routers and the ops endpoints, and on startup
wire projection writers onto the event bus and set up telemetry.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core import health
from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.logging import configure_logging, get_logger, request_id_ctx
from app.core.middleware import MetricsMiddleware, RequestContextMiddleware
from app.core.redis import close_redis, get_redis
from app.core.telemetry import setup_telemetry
from app.modules.cart.router import router as cart_router
from app.modules.orders.router import router as orders_router
from app.modules.pricing.router import router as pricing_router
from app.modules.products.router import router as products_router
from app.modules.users.router import router as users_router
from app.shared.dto import ErrorResponse
from app.shared.events import get_event_bus

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("app.startup", env=settings.app_env, service=settings.service_name)
    from app.bootstrap import wire_projections

    wire_projections(get_event_bus(), get_redis())
    yield
    logger.info("app.shutdown")
    await close_redis()
    await dispose_engine()


def _install_exception_handlers(app: FastAPI) -> None:
    from app.shared.exceptions import DomainError

    @app.exception_handler(DomainError)
    async def _domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        body = ErrorResponse(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            request_id=request_id_ctx.get(),
        )
        logger.info("domain.error", code=exc.code, message=exc.message)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        body = ErrorResponse(
            code="request_validation_error",
            message="Request validation failed",
            details={"errors": exc.errors()},
            request_id=request_id_ctx.get(),
        )
        return JSONResponse(status_code=422, content=body.model_dump())


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(level=settings.log_level, service_name=settings.service_name)

    app = FastAPI(
        title="commerce-platform",
        version="0.1.0",
        summary="Frontend-agnostic commerce API. Postgres is truth; Redis holds projections.",
        lifespan=lifespan,
    )

    # Order matters: request context is outermost so ids are bound before metrics
    # and handlers run.
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestContextMiddleware)

    _install_exception_handlers(app)

    app.include_router(health.router)
    api = settings.api_v1_prefix
    app.include_router(products_router, prefix=api)
    app.include_router(pricing_router, prefix=api)
    app.include_router(users_router, prefix=api)
    app.include_router(cart_router, prefix=api)
    app.include_router(orders_router, prefix=api)

    # Telemetry is set up after routers exist so the instrumentor sees all routes.
    setup_telemetry(app)
    return app


app = create_app()
