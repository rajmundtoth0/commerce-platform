"""Products HTTP API.

Writes go to Postgres via ProductService. The single-item read endpoint serves
from the Redis projection (the read model) and falls back to Postgres on a miss,
lazily backfilling the projection so the cache self-heals. List/admin reads go
straight to Postgres — projections are point lookups by id, not query indexes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.modules.products.projections import ProductProjectionWriter
from app.modules.products.schemas import (
    ProductCreate,
    ProductProjection,
    ProductRead,
    ProductUpdate,
)
from app.modules.products.service import ProductService
from app.shared.deps import BusDep, RedisDep, SessionDep
from app.shared.dto import Page

router = APIRouter(prefix="/products", tags=["products"])


def get_service(session: SessionDep, bus: BusDep) -> ProductService:
    return ProductService(session, bus)


def get_projection(redis: RedisDep) -> ProductProjectionWriter:
    return ProductProjectionWriter(redis)


ServiceDep = Annotated[ProductService, Depends(get_service)]
ProjectionDep = Annotated[ProductProjectionWriter, Depends(get_projection)]


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductCreate, service: ServiceDep) -> ProductRead:
    product = await service.create(data)
    return ProductRead.model_validate(product)


@router.get("", response_model=Page[ProductRead])
async def list_products(
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ProductRead]:
    items, total = await service.list(limit=limit, offset=offset)
    return Page[ProductRead](
        items=[ProductRead.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{product_id}", response_model=ProductProjection)
async def get_product(
    product_id: str,
    service: ServiceDep,
    projection: ProjectionDep,
) -> ProductProjection:
    """Read from the projection; on a miss, fall back to Postgres and backfill."""
    cached = await projection.read(product_id)
    if cached is not None:
        return cached

    product = await service.get(product_id)  # raises NotFoundError -> 404
    payload = ProductProjection.model_validate(product)
    await projection.write(product_id, payload)  # self-heal the cache
    return payload


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(product_id: str, data: ProductUpdate, service: ServiceDep) -> ProductRead:
    product = await service.update(product_id, data)
    return ProductRead.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str, service: ServiceDep) -> Response:
    await service.delete(product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
