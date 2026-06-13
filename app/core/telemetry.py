"""OpenTelemetry tracing setup.

Instrumentation for FastAPI, SQLAlchemy, and Redis is always wired in so that
spans are created and trace ids flow into logs. The OTLP exporter is only
attached when `OTEL_EXPORTER_OTLP_ENDPOINT` is configured — otherwise spans are
created but not exported, keeping local/test runs dependency-free.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

from app.core.config import get_settings
from app.core.database import get_engine
from app.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = get_logger(__name__)

_configured = False


def setup_telemetry(app: FastAPI) -> None:
    """Configure the tracer provider and instrument FastAPI/SQLAlchemy/Redis."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    resource = Resource.create({SERVICE_NAME: settings.service_name})
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBasedTraceIdRatio(settings.otel_traces_sampler_arg),
    )

    if settings.otel_enabled:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
        )
        logger.info("telemetry.exporter.enabled", endpoint=settings.otel_exporter_otlp_endpoint)
    else:
        logger.info("telemetry.exporter.disabled")

    trace.set_tracer_provider(provider)

    # FastAPIInstrumentor is imported lazily to avoid a hard import cycle with
    # the app module during startup.
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    SQLAlchemyInstrumentor().instrument(engine=get_engine().sync_engine, tracer_provider=provider)
    RedisInstrumentor().instrument(tracer_provider=provider)
    _configured = True


def current_trace_id() -> str | None:
    """Return the active trace id as a 32-char hex string, or None."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx is None or not ctx.is_valid:
        return None
    return format(ctx.trace_id, "032x")
