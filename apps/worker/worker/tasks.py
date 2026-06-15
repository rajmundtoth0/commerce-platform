"""Projection rebuild tasks.

Each task reads the OWNING service's authoritative database (sync) and writes the
versioned projection into Valkey via the shared `SyncProjectionWriter`. Tasks are
idempotent: rebuilding an entity that no longer exists deletes its projection
key, so the read model self-heals after deletes too.

Postgres stays the source of truth; Valkey is fully rebuildable from these tasks
(per-entity on change, plus the nightly full rebuild and stale-key cleanup).
"""

from __future__ import annotations

from typing import Any

from cplatform.celery_app import (
    TASK_CLEANUP_STALE,
    TASK_REBUILD_ALL,
    TASK_REBUILD_ORDER_SUMMARY,
    TASK_REBUILD_PRICE,
    TASK_REBUILD_PRODUCT,
)
from cplatform.contracts import ORDER_SUMMARY_SPEC, PRODUCT_PRICE_SPEC, PRODUCT_SPEC
from cplatform.logging import get_logger
from cplatform.metrics import PROJECTION_REBUILDS
from cplatform.projections import SyncProjectionWriter
from cplatform.sync_db import SyncDatabase
from cplatform.valkey import SyncValkey, get_sync_valkey
from worker.celery_app import celery
from worker.settings import settings

logger = get_logger("worker.tasks")
_settings = settings()

# Sync connections to the owning databases (sqlite/psycopg). The Valkey client is
# resolved lazily per call so test fixtures can inject a fake.
_backoffice_db = SyncDatabase(_settings.backoffice_postgres_dsn)
_orders_db = SyncDatabase(_settings.orders_postgres_dsn)


def _vk() -> SyncValkey:
    return get_sync_valkey(_settings.valkey_url)


def _product_writer() -> SyncProjectionWriter[Any]:
    return SyncProjectionWriter(PRODUCT_SPEC, _vk(), service=_settings.service_name)


def _price_writer() -> SyncProjectionWriter[Any]:
    return SyncProjectionWriter(PRODUCT_PRICE_SPEC, _vk(), service=_settings.service_name)


def _order_writer() -> SyncProjectionWriter[Any]:
    return SyncProjectionWriter(ORDER_SUMMARY_SPEC, _vk(), service=_settings.service_name)


@celery.task(name=TASK_REBUILD_PRODUCT)  # type: ignore[untyped-decorator]
def rebuild_product(product_id: str) -> str:
    from backoffice_api.rebuild import build_product

    with _backoffice_db.session() as session:
        projection = build_product(session, product_id)
    if projection is None:
        _product_writer().delete(product_id)  # product gone -> drop projection
        return "deleted"
    _product_writer().write(product_id, projection)
    return "written"


@celery.task(name=TASK_REBUILD_PRICE)  # type: ignore[untyped-decorator]
def rebuild_price(product_id: str) -> str:
    from backoffice_api.rebuild import build_price

    with _backoffice_db.session() as session:
        projection = build_price(session, product_id)
    if projection is None:
        _price_writer().delete(product_id)
        return "deleted"
    _price_writer().write(product_id, projection)
    return "written"


@celery.task(name=TASK_REBUILD_ORDER_SUMMARY)  # type: ignore[untyped-decorator]
def rebuild_order_summary(order_id: str) -> str:
    from orders_api.rebuild import build_order_summary

    with _orders_db.session() as session:
        projection = build_order_summary(session, order_id)
    if projection is None:
        _order_writer().delete(order_id)
        return "deleted"
    _order_writer().write(order_id, projection)
    return "written"


@celery.task(name=TASK_REBUILD_ALL)  # type: ignore[untyped-decorator]
def rebuild_all() -> dict[str, int]:
    """Full rebuild of every projection family from the authoritative databases."""
    from backoffice_api.rebuild import all_prices, all_products
    from orders_api.rebuild import all_order_summaries

    counts: dict[str, int] = {}
    try:
        _product_writer().clear()
        _price_writer().clear()
        with _backoffice_db.session() as session:
            counts["product"] = _rebuild_family(session, all_products, _product_writer())
            counts["product-price"] = _rebuild_family(session, all_prices, _price_writer())

        _order_writer().clear()
        with _orders_db.session() as session:
            counts["order-summary"] = _rebuild_family(session, all_order_summaries, _order_writer())
    except Exception:
        PROJECTION_REBUILDS.labels(_settings.service_name, "all", "error").inc()
        logger.error("worker.rebuild_all.failed", exc_info=True)
        raise

    for domain in counts:
        PROJECTION_REBUILDS.labels(_settings.service_name, domain, "ok").inc()
    logger.info("worker.rebuild_all.done", counts=counts)
    return counts


def _rebuild_family(session, iterator, writer) -> int:  # type: ignore[no-untyped-def]
    count = 0
    for entity_id, projection in iterator(session):
        writer.write(entity_id, projection)
        count += 1
    return count


@celery.task(name=TASK_CLEANUP_STALE)  # type: ignore[untyped-decorator]
def cleanup_stale() -> dict[str, int]:
    """Delete projection keys whose authoritative row no longer exists.

    Defends against missed delete events; the nightly rebuild_all also clears
    orphans, but this runs more often and only touches dangling keys.
    """
    from backoffice_api.rebuild import build_price, build_product
    from orders_api.rebuild import build_order_summary

    removed: dict[str, int] = {"product": 0, "product-price": 0, "order-summary": 0}

    with _backoffice_db.session() as session:
        for entity_id in _ids_for(PRODUCT_SPEC):
            if build_product(session, entity_id) is None:
                _product_writer().delete(entity_id)
                removed["product"] += 1
        for entity_id in _ids_for(PRODUCT_PRICE_SPEC):
            if build_price(session, entity_id) is None:
                _price_writer().delete(entity_id)
                removed["product-price"] += 1

    with _orders_db.session() as session:
        for entity_id in _ids_for(ORDER_SUMMARY_SPEC):
            if build_order_summary(session, entity_id) is None:
                _order_writer().delete(entity_id)
                removed["order-summary"] += 1

    logger.info("worker.cleanup_stale.done", removed=removed)
    return removed


def _ids_for(spec) -> list[str]:  # type: ignore[no-untyped-def]
    prefix = spec.key("")
    return [key[len(prefix) :] for key in _vk().scan_iter(match=spec.scan_pattern())]
