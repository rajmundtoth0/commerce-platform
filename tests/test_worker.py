"""Worker: per-entity rebuilds, full rebuild, and stale-key cleanup.

The worker reads the owning services' (sqlite, in tests) databases and writes the
versioned projections into the fake Valkey injected by the conftest fixture.
"""

from __future__ import annotations

import pytest

from cplatform.contracts import ORDER_SUMMARY_SPEC, PRODUCT_PRICE_SPEC, PRODUCT_SPEC
from cplatform.valkey import get_sync_valkey

pytestmark = pytest.mark.asyncio
VALKEY_URL = "redis://localhost:6379/0"


@pytest.fixture
def seeded():  # type: ignore[no-untyped-def]
    """Create owning-DB tables and seed one product+price and one order."""
    from backoffice_api.models import Base as BackofficeBase
    from backoffice_api.models import Product, ProductPrice
    from orders_api.models import Base as OrdersBase
    from orders_api.models import Order, OrderItem

    from worker import tasks

    BackofficeBase.metadata.create_all(tasks._backoffice_db.engine)
    OrdersBase.metadata.create_all(tasks._orders_db.engine)

    with tasks._backoffice_db.session() as s:
        s.add(
            Product(
                id="p1", sku="SKU-1", name="Widget", description="d", active=True, featured=True
            )
        )
        s.add(ProductPrice(product_id="p1", currency="USD", amount_minor=1999))
    with tasks._orders_db.session() as s:
        order = Order(
            id="o1", user_id="u1", status="created", currency="USD", total_amount_minor=3998
        )
        order.items.append(
            OrderItem(product_id="p1", product_name="Widget", quantity=2, unit_amount_minor=1999)
        )
        s.add(order)

    yield tasks

    BackofficeBase.metadata.drop_all(tasks._backoffice_db.engine)
    OrdersBase.metadata.drop_all(tasks._orders_db.engine)


def _decode(spec, entity_id):  # type: ignore[no-untyped-def]
    raw = get_sync_valkey(VALKEY_URL).get(spec.key(entity_id))
    return spec.decode(raw) if raw is not None else None


async def test_rebuild_product_and_price(seeded) -> None:  # type: ignore[no-untyped-def]
    assert seeded.rebuild_product("p1") == "written"
    assert seeded.rebuild_price("p1") == "written"

    product = _decode(PRODUCT_SPEC, "p1")
    price = _decode(PRODUCT_PRICE_SPEC, "p1")
    assert product is not None and product.featured is True and product.name == "Widget"
    assert price is not None and price.amount_minor == 1999


async def test_rebuild_order_summary(seeded) -> None:  # type: ignore[no-untyped-def]
    assert seeded.rebuild_order_summary("o1") == "written"
    summary = _decode(ORDER_SUMMARY_SPEC, "o1")
    assert summary is not None
    assert summary.item_count == 2
    assert summary.total_amount_minor == 3998


async def test_rebuild_missing_entity_deletes_key(seeded) -> None:  # type: ignore[no-untyped-def]
    seeded.rebuild_product("p1")
    assert _decode(PRODUCT_SPEC, "p1") is not None
    # Rebuild for an id with no backing row removes the projection.
    assert seeded.rebuild_product("ghost") == "deleted"
    assert _decode(PRODUCT_SPEC, "ghost") is None


async def test_rebuild_all(seeded) -> None:  # type: ignore[no-untyped-def]
    counts = seeded.rebuild_all()
    assert counts == {"product": 1, "product-price": 1, "order-summary": 1}
    assert _decode(PRODUCT_SPEC, "p1") is not None
    assert _decode(ORDER_SUMMARY_SPEC, "o1") is not None


async def test_cleanup_stale_removes_orphans(seeded) -> None:  # type: ignore[no-untyped-def]
    # Seed a projection key with no backing row.
    sync = get_sync_valkey(VALKEY_URL)
    seeded.rebuild_product("p1")
    sync.set(
        PRODUCT_SPEC.key("orphan"),
        '{"schema_version": 1, "data": {"id": "orphan", "sku": "x", "name": "n",'
        ' "description": "", "active": true, "featured": false}}',
    )
    removed = seeded.cleanup_stale()
    assert removed["product"] == 1  # only the orphan
    assert _decode(PRODUCT_SPEC, "orphan") is None
    assert _decode(PRODUCT_SPEC, "p1") is not None  # real product survives
