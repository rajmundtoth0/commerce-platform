"""Prometheus metrics shared across services.

A single default registry is exposed at /metrics on each service (and by the
worker's metrics server). Metrics are labeled by `service` so a single Prometheus
scrape distinguishes producers.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# --- HTTP ----------------------------------------------------------------
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests handled.",
    ["service", "method", "path", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["service", "method", "path"],
)

# --- Celery tasks ---------------------------------------------------------
TASK_DURATION = Histogram(
    "celery_task_duration_seconds",
    "Celery task execution time in seconds.",
    ["service", "task"],
)
TASK_FAILURES = Counter(
    "celery_task_failures_total",
    "Celery task failures.",
    ["service", "task"],
)

# --- Projections (Valkey read model) -------------------------------------
PROJECTION_WRITES = Counter(
    "projection_writes_total",
    "Valkey projection writes.",
    ["service", "domain", "result"],  # result: ok|error
)
PROJECTION_READS = Counter(
    "projection_reads_total",
    "Valkey projection reads.",
    ["service", "domain", "result"],  # result: hit|miss|stale
)
PROJECTION_REBUILDS = Counter(
    "projection_rebuilds_total",
    "Projection rebuild runs.",
    ["service", "domain", "result"],  # result: ok|error
)


def render_latest() -> tuple[bytes, str]:
    """Return (payload, content_type) for a /metrics response."""
    return generate_latest(), CONTENT_TYPE_LATEST
