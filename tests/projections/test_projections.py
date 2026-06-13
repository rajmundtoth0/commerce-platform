"""Projection writer/reader contract + full rebuild from Postgres."""

from __future__ import annotations

import json

import pytest
from app.bootstrap import rebuild_all
from app.modules.pricing.projections import ProductPriceProjectionWriter
from app.modules.pricing.schemas import PriceUpsert
from app.modules.pricing.service import PricingService
from app.modules.products.projections import ProductProjectionWriter
from app.modules.products.schemas import ProductCreate, ProductProjection
from app.modules.products.service import ProductService
from app.shared.events import EventBus
from app.shared.projection import Envelope

pytestmark = pytest.mark.asyncio


async def test_key_format_is_versioned_contract(redis) -> None:
    writer = ProductProjectionWriter(redis)
    assert writer.key("abc") == "dk:product:v1:abc"
    price = ProductPriceProjectionWriter(redis)
    assert price.key("abc") == "dk:product-price:v1:abc"


async def test_write_then_read_roundtrip(redis) -> None:
    writer = ProductProjectionWriter(redis)
    payload = ProductProjection(id="x", sku="SK", name="N", description="", active=True)
    await writer.write("x", payload)

    assert await writer.read("x") == payload

    # The stored value is a self-describing envelope.
    raw = await redis.get("dk:product:v1:x")
    envelope = Envelope.model_validate_json(raw)
    assert envelope.schema_version == 1
    assert envelope.data["sku"] == "SK"


async def test_schema_version_mismatch_is_treated_as_miss(redis) -> None:
    writer = ProductProjectionWriter(redis)
    # Simulate a payload written by an older/newer schema version.
    stale = Envelope(
        schema_version=999,
        data={"id": "x", "sku": "S", "name": "N", "description": "", "active": True},
    )
    await redis.set("dk:product:v1:x", stale.model_dump_json())
    assert await writer.read("x") is None


async def test_read_miss_returns_none(redis) -> None:
    assert await ProductProjectionWriter(redis).read("absent") is None


async def test_rebuild_repairs_drift(session, redis) -> None:
    # Seed authoritative data WITHOUT events (throwaway bus), so Redis is empty.
    silent_bus = EventBus()
    products = ProductService(session, silent_bus)
    pricing = PricingService(session, silent_bus)
    p = await products.create(ProductCreate(sku="RB", name="Rebuildable"))
    await pricing.upsert(p.id, PriceUpsert(currency="EUR", amount_minor=4200))
    await session.commit()

    # Nothing in the read model yet.
    assert await ProductProjectionWriter(redis).read(p.id) is None

    counts = await rebuild_all(session, redis)
    assert counts == {"product": 1, "product-price": 1}

    product_proj = await ProductProjectionWriter(redis).read(p.id)
    price_proj = await ProductPriceProjectionWriter(redis).read(p.id)
    assert product_proj is not None and product_proj.name == "Rebuildable"
    assert price_proj is not None and price_proj.amount_minor == 4200


async def test_rebuild_clears_orphaned_keys(session, redis) -> None:
    # An orphan projection that no longer has a backing row must be removed.
    await redis.set(
        "dk:product:v1:orphan",
        json.dumps(
            {
                "schema_version": 1,
                "data": {
                    "id": "orphan",
                    "sku": "O",
                    "name": "x",
                    "description": "",
                    "active": True,
                },
            }
        ),
    )
    await rebuild_all(session, redis)
    assert await redis.get("dk:product:v1:orphan") is None
