from __future__ import annotations

from cplatform.celery_app import TASK_REBUILD_ORDER_SUMMARY, make_celery
from cplatform.logging import get_logger
from orders_api.settings import settings

_settings = settings()
logger = get_logger(_settings.service_name)

celery = make_celery(
    name="orders-api",
    broker_url=_settings.celery_broker_url,
    result_backend=_settings.celery_result_backend,
)


def enqueue_order_summary(order_id: str) -> None:
    """Best-effort enqueue of an order-summary rebuild.

    Enqueue failures must NOT fail the request: the nightly rebuild reconciles
    any projection that was missed here.
    """
    try:
        celery.send_task(TASK_REBUILD_ORDER_SUMMARY, args=[order_id])
    except Exception as exc:  # pragma: no cover - exercised via broker failures
        logger.warning("orders.enqueue.order_summary.failed", order_id=order_id, error=str(exc))
