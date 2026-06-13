"""Product-price projection writer + event subscriptions.

Key:     dk:product-price:v1:{product_id}
Payload: ProductPriceProjection (schema_version 1)
"""

from __future__ import annotations

from app.modules.pricing.schemas import ProductPriceProjection
from app.shared.events import EventBus, PriceDeleted, PriceUpserted
from app.shared.projection import RedisProjection


class ProductPriceProjectionWriter(RedisProjection[ProductPriceProjection]):
    name = "product-price"
    key_version = 1
    schema_version = 1
    model = ProductPriceProjection

    async def on_upserted(self, event: PriceUpserted) -> None:
        await self.write(
            event.product_id,
            ProductPriceProjection(
                product_id=event.product_id,
                currency=event.currency,
                amount_minor=event.amount_minor,
            ),
        )

    async def on_deleted(self, event: PriceDeleted) -> None:
        await self.delete(event.product_id)


def register(bus: EventBus, writer: ProductPriceProjectionWriter) -> None:
    bus.subscribe(PriceUpserted, writer.on_upserted)
    bus.subscribe(PriceDeleted, writer.on_deleted)
