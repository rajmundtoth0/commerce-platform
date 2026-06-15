"""Structured JSON logging with a rich request/task context.

Every log line is one JSON object and automatically carries correlation fields
bound for the current request or Celery task:

  service       — which service emitted the line
  request_id    — per HTTP request (or task id for Celery work)
  trace_id      — active OpenTelemetry trace
  task_id       — Celery task id, when running in a worker
  domain        — domain/module (e.g. "product", "order")
  projection_key / projection_version — set when (re)building projections

Code binds these via `bind_context(...)` (contextvars), so a value set at the
edge of a request flows into every line emitted while handling it without being
threaded through call signatures.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog

_CONTEXT_FIELDS = (
    "request_id",
    "trace_id",
    "task_id",
    "domain",
    "projection_key",
    "projection_version",
)


def configure_logging(level: str = "INFO", service_name: str = "service") -> None:
    """Configure structlog + stdlib logging to emit JSON to stdout. Idempotent."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared,
            structlog.processors.EventRenamer("message"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared,
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service=service_name)


def bind_context(**fields: Any) -> None:
    """Bind correlation fields onto the current context (request/task scoped)."""
    clean = {k: v for k, v in fields.items() if v is not None}
    if clean:
        structlog.contextvars.bind_contextvars(**clean)


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    from typing import cast

    return cast("structlog.stdlib.BoundLogger", structlog.get_logger(name))


__all__ = ["_CONTEXT_FIELDS", "bind_context", "clear_context", "configure_logging", "get_logger"]
