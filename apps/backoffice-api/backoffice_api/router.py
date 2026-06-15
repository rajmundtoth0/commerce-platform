from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from backoffice_api.deps import AdminUser, ServiceDep
from backoffice_api.schemas import (
    PriceRead,
    PriceUpsert,
    ProductCreate,
    ProductList,
    ProductRead,
    ProductUpdate,
)
from backoffice_api.tasks import (
    enqueue_price_rebuild,
    enqueue_product_rebuild,
    enqueue_rebuild_all,
)
from cplatform.celery_app import TASK_REBUILD_ALL
from cplatform.contracts import PRODUCT_PRICE_SPEC, PRODUCT_SPEC

products_router = APIRouter(prefix="/products", tags=["products"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


# --- products ------------------------------------------------------------
@products_router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate, _admin: AdminUser, service: ServiceDep
) -> ProductRead:
    product = await service.create_product(data)
    enqueue_product_rebuild(product.id)
    return ProductRead.model_validate(product)


@products_router.get("", response_model=ProductList)
async def list_products(
    _admin: AdminUser,
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductList:
    items, total = await service.list_products(limit=limit, offset=offset)
    return ProductList(
        items=[ProductRead.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@products_router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: str, _admin: AdminUser, service: ServiceDep) -> ProductRead:
    return ProductRead.model_validate(await service.get_product(product_id))


@products_router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: str, data: ProductUpdate, _admin: AdminUser, service: ServiceDep
) -> ProductRead:
    product = await service.update_product(product_id, data)
    enqueue_product_rebuild(product.id)
    return ProductRead.model_validate(product)


@products_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str, _admin: AdminUser, service: ServiceDep) -> Response:
    await service.delete_product(product_id)
    # Rebuild so the worker cleans up the now-stale projection key.
    enqueue_product_rebuild(product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- prices --------------------------------------------------------------
@products_router.put("/{product_id}/price", response_model=PriceRead)
async def upsert_price(
    product_id: str, data: PriceUpsert, _admin: AdminUser, service: ServiceDep
) -> PriceRead:
    price = await service.upsert_price(product_id, data)
    enqueue_price_rebuild(product_id)
    return PriceRead.model_validate(price)


@products_router.get("/{product_id}/price", response_model=PriceRead)
async def get_price(product_id: str, _admin: AdminUser, service: ServiceDep) -> PriceRead:
    return PriceRead.model_validate(await service.get_price(product_id))


@products_router.delete("/{product_id}/price", status_code=status.HTTP_204_NO_CONTENT)
async def delete_price(product_id: str, _admin: AdminUser, service: ServiceDep) -> Response:
    await service.delete_price(product_id)
    enqueue_price_rebuild(product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- admin / projections -------------------------------------------------
@admin_router.post("/projections/rebuild", status_code=status.HTTP_202_ACCEPTED)
async def rebuild_all_projections(_admin: AdminUser) -> dict[str, object]:
    enqueue_rebuild_all()
    return {"enqueued": True, "task": TASK_REBUILD_ALL}


@admin_router.get("/projections")
async def list_projections(_admin: AdminUser) -> list[dict[str, object]]:
    return [PRODUCT_SPEC.metadata(), PRODUCT_PRICE_SPEC.metadata()]
