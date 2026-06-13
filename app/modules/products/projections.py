"""Product projection writer + event subscriptions.

Key:    dk:product:v1:{product_id}
Payload: ProductProjection (schema_version 1)
"""

from __future__ import annotations

from app.modules.products.schemas import ProductProjection
from app.shared.events import EventBus, ProductDeleted, ProductUpserted
from app.shared.projection import RedisProjection


class ProductProjectionWriter(RedisProjection[ProductProjection]):
    name = "product"
    key_version = 1
    schema_version = 1
    model = ProductProjection

    async def on_upserted(self, event: ProductUpserted) -> None:
        await self.write(
            event.product_id,
            ProductProjection(
                id=event.product_id,
                sku=event.sku,
                name=event.name,
                description=event.description,
                active=event.active,
            ),
        )

    async def on_deleted(self, event: ProductDeleted) -> None:
        await self.delete(event.product_id)


def register(bus: EventBus, writer: ProductProjectionWriter) -> None:
    """Wire this writer's handlers onto the event bus."""
    bus.subscribe(ProductUpserted, writer.on_upserted)
    bus.subscribe(ProductDeleted, writer.on_deleted)
