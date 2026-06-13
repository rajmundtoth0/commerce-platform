"""Service-level tests: write model + event-driven projection updates."""

from __future__ import annotations

import pytest
from app.modules.products.projections import ProductProjectionWriter
from app.modules.products.schemas import ProductCreate, ProductUpdate
from app.modules.products.service import ProductService
from app.shared.events import get_event_bus
from app.shared.exceptions import ConflictError, NotFoundError

pytestmark = pytest.mark.asyncio


async def test_create_publishes_event_and_writes_projection(session, redis) -> None:
    service = ProductService(session, get_event_bus())
    product = await service.create(ProductCreate(sku="S1", name="Thing"))
    await session.commit()

    projection = await ProductProjectionWriter(redis).read(product.id)
    assert projection is not None
    assert projection.name == "Thing"
    assert projection.sku == "S1"


async def test_update_then_projection_reflects_change(session, redis) -> None:
    service = ProductService(session, get_event_bus())
    product = await service.create(ProductCreate(sku="S2", name="Old"))
    await service.update(product.id, ProductUpdate(name="New"))
    await session.commit()

    projection = await ProductProjectionWriter(redis).read(product.id)
    assert projection is not None and projection.name == "New"


async def test_delete_removes_projection(session, redis) -> None:
    service = ProductService(session, get_event_bus())
    product = await service.create(ProductCreate(sku="S3", name="Gone"))
    await service.delete(product.id)
    await session.commit()

    assert await ProductProjectionWriter(redis).read(product.id) is None


async def test_duplicate_sku_raises_conflict(session) -> None:
    service = ProductService(session, get_event_bus())
    await service.create(ProductCreate(sku="DUP", name="A"))
    with pytest.raises(ConflictError):
        await service.create(ProductCreate(sku="DUP", name="B"))


async def test_get_missing_raises_not_found(session) -> None:
    service = ProductService(session, get_event_bus())
    with pytest.raises(NotFoundError):
        await service.get("nope")
