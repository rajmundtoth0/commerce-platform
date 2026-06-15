"""Celery application for the worker.

Builds the Celery app (Valkey broker/backend), wires task observability + OTel,
starts a Prometheus metrics endpoint, and registers the Beat schedule for the
nightly full rebuild and stale-key cleanup. Tasks are defined in worker.tasks
and imported here so the worker registers them.
"""

from __future__ import annotations

from typing import Any

from celery.schedules import crontab
from celery.signals import worker_process_init
from prometheus_client import start_http_server

from cplatform.celery_app import (
    TASK_CLEANUP_STALE,
    TASK_REBUILD_ALL,
    install_task_observability,
    make_celery,
)
from cplatform.logging import configure_logging, get_logger
from cplatform.telemetry import setup_worker_telemetry
from worker.settings import settings

_settings = settings()
configure_logging(level=_settings.log_level, service_name=_settings.service_name)
logger = get_logger("worker")

celery = make_celery(
    name="worker",
    broker_url=_settings.celery_broker_url,
    result_backend=_settings.celery_result_backend,
)
celery.autodiscover_tasks(["worker"])

install_task_observability(_settings.service_name)
setup_worker_telemetry(
    service_name=_settings.service_name,
    endpoint=_settings.otel_exporter_otlp_endpoint,
    sampler_arg=_settings.otel_traces_sampler_arg,
)

# Scheduled maintenance: nightly full rebuild + hourly stale-key cleanup.
celery.conf.beat_schedule = {
    "nightly-full-rebuild": {
        "task": TASK_REBUILD_ALL,
        "schedule": crontab(hour="3", minute="0"),
    },
    "hourly-stale-cleanup": {
        "task": TASK_CLEANUP_STALE,
        "schedule": crontab(minute="0"),
    },
}


@worker_process_init.connect  # type: ignore[untyped-decorator]
def _start_metrics_server(**_: Any) -> None:
    try:
        start_http_server(_settings.metrics_port)
        logger.info("worker.metrics.started", port=_settings.metrics_port)
    except OSError as exc:  # port already bound by another process in the pool
        logger.warning("worker.metrics.skip", error=str(exc))


# Tasks are registered via autodiscover_tasks(["worker"]) above when the worker
# starts; worker.tasks imports `celery` from this module (no import cycle).
