"""Structured JSON logging.

Every log line is a single JSON object. A request-scoped context (request id +
trace id) is bound via `contextvars` so that all log lines emitted while handling
a request automatically carry correlation identifiers — without threading a
logger through every call.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any, cast

import structlog

# Request-scoped correlation ids. Populated by RequestContextMiddleware.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)


def _inject_request_context(
    _logger: Any, _method: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """structlog processor that adds correlation ids when present."""
    request_id = request_id_ctx.get()
    trace_id = trace_id_ctx.get()
    if request_id is not None:
        event_dict["request_id"] = request_id
    if trace_id is not None:
        event_dict["trace_id"] = trace_id
    return event_dict


def configure_logging(level: str = "INFO", service_name: str = "commerce-platform") -> None:
    """Configure structlog + stdlib logging to emit JSON to stdout.

    Idempotent: safe to call multiple times (e.g. from app startup and tests).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _inject_request_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.EventRenamer("message"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging (uvicorn, sqlalchemy, etc.) through the same renderer.
    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Bind the service name into the global context for every line.
    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return cast("structlog.stdlib.BoundLogger", structlog.get_logger(name))
