"""Pricing HTTP API. Reads serve from the product-price projection."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.modules.pricing.projections import ProductPriceProjectionWriter
from app.modules.pricing.schemas import PriceRead, PriceUpsert, ProductPriceProjection
from app.modules.pricing.service import PricingService
from app.shared.deps import BusDep, RedisDep, SessionDep

router = APIRouter(prefix="/products/{product_id}/price", tags=["pricing"])


def get_service(session: SessionDep, bus: BusDep) -> PricingService:
    return PricingService(session, bus)


def get_projection(redis: RedisDep) -> ProductPriceProjectionWriter:
    return ProductPriceProjectionWriter(redis)


ServiceDep = Annotated[PricingService, Depends(get_service)]
ProjectionDep = Annotated[ProductPriceProjectionWriter, Depends(get_projection)]


@router.put("", response_model=PriceRead)
async def set_price(product_id: str, data: PriceUpsert, service: ServiceDep) -> PriceRead:
    price = await service.upsert(product_id, data)
    return PriceRead.model_validate(price)


@router.get("", response_model=ProductPriceProjection)
async def get_price(
    product_id: str, service: ServiceDep, projection: ProjectionDep
) -> ProductPriceProjection:
    cached = await projection.read(product_id)
    if cached is not None:
        return cached
    price = await service.get(product_id)  # raises NotFoundError -> 404
    payload = ProductPriceProjection.model_validate(price)
    await projection.write(product_id, payload)
    return payload


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_price(product_id: str, service: ServiceDep) -> Response:
    await service.delete(product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
