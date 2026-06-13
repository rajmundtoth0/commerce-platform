"""Prometheus-compatible metrics.

A single default registry is exposed at /metrics. We define application-level
metrics here (HTTP, projections) so operators can answer "are projections being
written?" and "are reads hitting the cache?" without reading logs.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# --- HTTP ----------------------------------------------------------------
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests handled.",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
)

# --- Projections ----------------------------------------------------------
# `result` is "ok"/"error" for writes and "hit"/"miss"/"stale" for reads, so a
# rising miss/stale rate is immediately graphable.
PROJECTION_WRITES = Counter(
    "projection_writes_total",
    "Read-model projection writes.",
    ["domain", "result"],
)
PROJECTION_READS = Counter(
    "projection_reads_total",
    "Read-model projection reads.",
    ["domain", "result"],
)
PROJECTION_REBUILDS = Counter(
    "projection_rebuilds_total",
    "Full projection rebuild runs.",
    ["domain", "result"],
)


def render_latest() -> tuple[bytes, str]:
    """Return (payload, content_type) for the /metrics endpoint."""
    return generate_latest(), CONTENT_TYPE_LATEST
