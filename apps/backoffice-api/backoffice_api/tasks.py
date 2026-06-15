"""Celery enqueue helpers (producer side).

backoffice-api owns authoritative product/price data; after every write it
enqueues a projection-rebuild task by *name* (the queue is the contract — it
never imports worker code). Enqueue failures are logged but never fail the
write: the projection is eventually-consistent and can be rebuilt out of band.
"""

from __future__ import annotations

from backoffice_api.settings import settings
from cplatform.celery_app import (
    TASK_REBUILD_ALL,
    TASK_REBUILD_PRICE,
    TASK_REBUILD_PRODUCT,
    make_celery,
)
from cplatform.logging import get_logger

_settings = settings()
logger = get_logger(_settings.service_name)

celery = make_celery(
    name="backoffice-api",
    broker_url=_settings.celery_broker_url,
    result_backend=_settings.celery_result_backend,
)


def _send(task_name: str, *args: object) -> None:
    try:
        celery.send_task(task_name, args=list(args))
    except Exception as exc:  # enqueue failure must not fail the write.
        logger.warning("projection.enqueue.failed", task=task_name, args=args, error=str(exc))


def enqueue_product_rebuild(product_id: str) -> None:
    _send(TASK_REBUILD_PRODUCT, product_id)


def enqueue_price_rebuild(product_id: str) -> None:
    _send(TASK_REBUILD_PRICE, product_id)


def enqueue_rebuild_all() -> None:
    _send(TASK_REBUILD_ALL)
