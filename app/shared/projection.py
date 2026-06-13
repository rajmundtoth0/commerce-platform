"""Projection infrastructure: versioned Redis read-model keys.

Projection keys are a *contract*. The public API and any external consumer may
depend on the key format and the payload schema, so both are versioned:

    dk:{name}:v{key_version}:{entity_id}
    └┬┘ └─┬─┘ └──────┬──────┘ └────┬────┘
  namespace name   key version   entity id

`dk` is the fixed namespace ("data kernel"). The *key version* changes when the
key layout or identity changes (a breaking change for consumers); the *schema
version* (stored inside the JSON envelope) changes when the payload shape
evolves. Readers validate the schema version and treat a mismatch as a miss, so
a half-migrated cache degrades to "rebuild needed" rather than serving garbage.

Every projection type subclasses `RedisProjection`, which is the single place
that knows how to (de)serialize the envelope, build keys, and emit metrics. The
*same* `build`-fed `write` path is used by both the event-driven writers and the
full-rebuild job — there is exactly one way a projection is produced.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic import BaseModel

from app.core.logging import get_logger
from app.core.metrics import PROJECTION_READS, PROJECTION_WRITES
from app.core.redis import RedisClient

logger = get_logger(__name__)

NAMESPACE = "dk"


class Envelope(BaseModel):
    """Wire format stored at each projection key.

    Storing the versions alongside the data makes every cached value
    self-describing — a reader can decide whether it understands a payload
    without consulting external state.
    """

    schema_version: int
    data: dict[str, object]


class RedisProjection[ModelT: BaseModel]:
    """Base class for a single projection family (e.g. product, product-price)."""

    # Subclasses MUST set these. They are the projection's public contract.
    name: str
    key_version: int
    schema_version: int
    model: type[ModelT]

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    # --- Key layout -------------------------------------------------------
    def key(self, entity_id: str) -> str:
        return f"{NAMESPACE}:{self.name}:v{self.key_version}:{entity_id}"

    def _scan_pattern(self) -> str:
        return f"{NAMESPACE}:{self.name}:v{self.key_version}:*"

    # --- Writes -----------------------------------------------------------
    async def write(self, entity_id: str, payload: ModelT) -> None:
        """Serialize and store one projection value."""
        envelope = Envelope(
            schema_version=self.schema_version, data=payload.model_dump(mode="json")
        )
        try:
            await self._redis.set(self.key(entity_id), envelope.model_dump_json())
            PROJECTION_WRITES.labels(domain=self.name, result="ok").inc()
            logger.debug("projection.write", domain=self.name, entity_id=entity_id)
        except Exception:
            PROJECTION_WRITES.labels(domain=self.name, result="error").inc()
            logger.error(
                "projection.write.failed", domain=self.name, entity_id=entity_id, exc_info=True
            )
            raise

    async def delete(self, entity_id: str) -> None:
        await self._redis.delete(self.key(entity_id))
        logger.debug("projection.delete", domain=self.name, entity_id=entity_id)

    # --- Reads ------------------------------------------------------------
    async def read(self, entity_id: str) -> ModelT | None:
        """Return the projected value, or None on miss / schema mismatch."""
        raw = await self._redis.get(self.key(entity_id))
        if raw is None:
            PROJECTION_READS.labels(domain=self.name, result="miss").inc()
            return None
        envelope = Envelope.model_validate_json(raw)
        if envelope.schema_version != self.schema_version:
            # Known key, payload we no longer understand: treat as stale.
            PROJECTION_READS.labels(domain=self.name, result="stale").inc()
            logger.warning(
                "projection.read.stale",
                domain=self.name,
                entity_id=entity_id,
                found=envelope.schema_version,
                expected=self.schema_version,
            )
            return None
        PROJECTION_READS.labels(domain=self.name, result="hit").inc()
        return self.model.model_validate(envelope.data)

    # --- Maintenance ------------------------------------------------------
    async def iter_keys(self) -> AsyncIterator[str]:
        async for key in self._redis.scan_iter(match=self._scan_pattern()):
            yield key

    async def clear(self) -> int:
        """Delete every key in this projection family. Returns count removed."""
        removed = 0
        async for key in self.iter_keys():
            await self._redis.delete(key)
            removed += 1
        return removed
