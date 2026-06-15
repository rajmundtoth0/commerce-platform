"""Domain error hierarchy + a FastAPI handler installer.

Services raise these domain errors; `install_error_handlers(app)` maps them to a
consistent JSON error envelope so every service answers errors the same way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from fastapi import FastAPI


class DomainError(Exception):
    code: str = "domain_error"
    status_code: int = 400

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(DomainError):
    code = "not_found"
    status_code = 404


class ConflictError(DomainError):
    code = "conflict"
    status_code = 409


class ValidationError(DomainError):
    code = "validation_error"
    status_code = 422


class AuthError(DomainError):
    code = "unauthorized"
    status_code = 401


class ForbiddenError(DomainError):
    code = "forbidden"
    status_code = 403


class UpstreamError(DomainError):
    """A dependency service (e.g. orders-api) failed or was unreachable."""

    code = "upstream_error"
    status_code = 502


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)
    request_id: str | None = None


def install_error_handlers(app: FastAPI) -> None:
    from fastapi import Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    from cplatform.logging import get_logger

    logger = get_logger("errors")

    def _request_id() -> str | None:
        import structlog

        return structlog.contextvars.get_contextvars().get("request_id")

    @app.exception_handler(DomainError)
    async def _domain(_request: Request, exc: DomainError) -> JSONResponse:
        logger.info("domain.error", code=exc.code, message=exc.message)
        body = ErrorResponse(
            code=exc.code, message=exc.message, details=exc.details, request_id=_request_id()
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        body = ErrorResponse(
            code="request_validation_error",
            message="Request validation failed",
            details={"errors": exc.errors()},
            request_id=_request_id(),
        )
        return JSONResponse(status_code=422, content=body.model_dump())
