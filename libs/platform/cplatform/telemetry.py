"""OpenTelemetry setup for services and the worker.

Instrumentation for FastAPI, SQLAlchemy, Redis/Valkey, and Celery is always
wired so spans exist and trace ids reach the logs. The OTLP exporter is attached
only when an endpoint is configured, keeping local/test runs collector-free.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

from cplatform.logging import get_logger

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = get_logger("telemetry")

_provider: TracerProvider | None = None


def _provider_for(service_name: str, *, endpoint: str, sampler_arg: float) -> TracerProvider:
    global _provider
    if _provider is not None:
        return _provider
    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: service_name}),
        sampler=ParentBasedTraceIdRatio(sampler_arg),
    )
    if endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        logger.info("telemetry.exporter.enabled", endpoint=endpoint)
    trace.set_tracer_provider(provider)
    _provider = provider
    return provider


def setup_fastapi_telemetry(
    app: FastAPI,
    *,
    service_name: str,
    endpoint: str,
    sampler_arg: float,
    engine: Any | None = None,
) -> None:
    provider = _provider_for(service_name, endpoint=endpoint, sampler_arg=sampler_arg)

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    RedisInstrumentor().instrument(tracer_provider=provider)
    if engine is not None:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        sync_engine = getattr(engine, "sync_engine", engine)
        SQLAlchemyInstrumentor().instrument(engine=sync_engine, tracer_provider=provider)


def setup_worker_telemetry(*, service_name: str, endpoint: str, sampler_arg: float) -> None:
    provider = _provider_for(service_name, endpoint=endpoint, sampler_arg=sampler_arg)
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    CeleryInstrumentor().instrument(tracer_provider=provider)  # type: ignore[no-untyped-call]
    RedisInstrumentor().instrument(tracer_provider=provider)


def current_trace_id() -> str | None:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx is None or not ctx.is_valid:
        return None
    return format(ctx.trace_id, "032x")
