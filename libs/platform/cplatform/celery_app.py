"""Celery application factory + task instrumentation.

The worker uses Valkey as broker and result backend. Producers (API services)
import `make_celery` to get a client they enqueue onto by task *name*
(`send_task`), so they never import worker code — the queue is the contract.
"""

from __future__ import annotations

import time
from typing import Any

from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun

from cplatform.logging import bind_context, clear_context, configure_logging, get_logger
from cplatform.metrics import TASK_DURATION, TASK_FAILURES

logger = get_logger("celery")

# Stable task names — the enqueue/execute contract between services and worker.
TASK_REBUILD_PRODUCT = "projections.rebuild_product"
TASK_REBUILD_PRICE = "projections.rebuild_price"
TASK_REBUILD_ORDER_SUMMARY = "projections.rebuild_order_summary"
TASK_REBUILD_ALL = "projections.rebuild_all"
TASK_CLEANUP_STALE = "projections.cleanup_stale"


def make_celery(*, name: str, broker_url: str, result_backend: str) -> Celery:
    app = Celery(name, broker=broker_url, backend=result_backend)
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        result_expires=3600,
    )
    return app


_starts: dict[str, float] = {}


def install_task_observability(service_name: str) -> None:
    """Wire structured logging + metrics around task execution."""

    @task_prerun.connect  # type: ignore[untyped-decorator]
    def _prerun(task_id: str | None = None, task: Any = None, **_: Any) -> None:
        configure_logging(service_name=service_name)
        bind_context(service=service_name, task_id=task_id, request_id=task_id)
        if task_id:
            _starts[task_id] = time.perf_counter()
        logger.info("task.start", task=getattr(task, "name", "?"))

    @task_postrun.connect  # type: ignore[untyped-decorator]
    def _postrun(task_id: str | None = None, task: Any = None, **_: Any) -> None:
        name = getattr(task, "name", "?")
        started = _starts.pop(task_id, None) if task_id else None
        if started is not None:
            TASK_DURATION.labels(service_name, name).observe(time.perf_counter() - started)
        logger.info("task.done", task=name)
        clear_context()

    @task_failure.connect  # type: ignore[untyped-decorator]
    def _failure(task_id: str | None = None, sender: Any = None, **_: Any) -> None:
        name = getattr(sender, "name", "?")
        TASK_FAILURES.labels(service_name, name).inc()
        logger.error("task.failed", task=name, task_id=task_id)
