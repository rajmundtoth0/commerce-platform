"""Versioned projection contracts (the read model in Valkey).

Projection keys are an explicit, versioned contract that API consumers depend on
*instead of* the database schema:

    dk:{name}:v{key_version}:{entity_id}
    e.g. dk:product:v1:{product_id}
         dk:product-price:v1:{product_id}
         dk:order-summary:v1:{order_id}

Each value is a self-describing envelope `{schema_version, data}`. The key
version changes on a breaking key/identity change; the schema version changes
when the payload shape evolves. Readers treat a schema mismatch as a miss
(counted `stale`) so a half-migrated cache degrades to "rebuild needed" rather
than serving payloads consumers can't parse.

A `ProjectionSpec` defines one projection family and is shared by:
  * `AsyncProjectionReader` — used by API services to read.
  * `SyncProjectionWriter`  — used by the Celery worker to (re)build.

There is exactly one key layout and one envelope codec, so producer and consumer
can never drift.
"""

from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel

from cplatform.logging import bind_context, get_logger
from cplatform.metrics import PROJECTION_READS, PROJECTION_WRITES
from cplatform.valkey import AsyncValkey, SyncValkey

logger = get_logger("projections")

NAMESPACE = "dk"


class Envelope(BaseModel):
    schema_version: int
    data: dict[str, object]


class ProjectionSpec[ModelT: BaseModel]:
    """Defines one projection family: its name, versions, and payload model."""

    def __init__(
        self, *, name: str, key_version: int, schema_version: int, model: type[ModelT]
    ) -> None:
        self.name = name
        self.key_version = key_version
        self.schema_version = schema_version
        self.model = model

    def key(self, entity_id: str) -> str:
        return f"{NAMESPACE}:{self.name}:v{self.key_version}:{entity_id}"

    def scan_pattern(self) -> str:
        return f"{NAMESPACE}:{self.name}:v{self.key_version}:*"

    def encode(self, payload: ModelT) -> str:
        return Envelope(
            schema_version=self.schema_version, data=payload.model_dump(mode="json")
        ).model_dump_json()

    def decode(self, raw: str | bytes) -> ModelT | None:
        """Return the payload, or None if the schema version is not understood."""
        envelope = Envelope.model_validate_json(raw)
        if envelope.schema_version != self.schema_version:
            return None
        return self.model.model_validate(envelope.data)

    def metadata(self) -> dict[str, object]:
        return {
            "name": self.name,
            "key_version": self.key_version,
            "schema_version": self.schema_version,
            "namespace": NAMESPACE,
            "key_template": self.key("{entity_id}"),
        }


class AsyncProjectionReader[ModelT: BaseModel]:
    """Read projections from Valkey (used by API services)."""

    def __init__(self, spec: ProjectionSpec[ModelT], client: AsyncValkey, *, service: str) -> None:
        self._spec = spec
        self._client = client
        self._service = service

    async def read(self, entity_id: str) -> ModelT | None:
        raw = await self._client.get(self._spec.key(entity_id))
        if raw is None:
            PROJECTION_READS.labels(self._service, self._spec.name, "miss").inc()
            return None
        payload = self._spec.decode(raw)
        if payload is None:
            PROJECTION_READS.labels(self._service, self._spec.name, "stale").inc()
            logger.warning(
                "projection.read.stale",
                domain=self._spec.name,
                projection_key=self._spec.key(entity_id),
                projection_version=self._spec.schema_version,
            )
            return None
        PROJECTION_READS.labels(self._service, self._spec.name, "hit").inc()
        return payload

    async def read_many(self, entity_ids: list[str]) -> dict[str, ModelT]:
        out: dict[str, ModelT] = {}
        for entity_id in entity_ids:
            payload = await self.read(entity_id)
            if payload is not None:
                out[entity_id] = payload
        return out


class SyncProjectionWriter[ModelT: BaseModel]:
    """Write/rebuild projections in Valkey (used by the Celery worker)."""

    def __init__(self, spec: ProjectionSpec[ModelT], client: SyncValkey, *, service: str) -> None:
        self._spec = spec
        self._client = client
        self._service = service

    def write(self, entity_id: str, payload: ModelT) -> None:
        key = self._spec.key(entity_id)
        bind_context(
            domain=self._spec.name, projection_key=key, projection_version=self._spec.schema_version
        )
        try:
            self._client.set(key, self._spec.encode(payload))
            PROJECTION_WRITES.labels(self._service, self._spec.name, "ok").inc()
        except Exception:
            PROJECTION_WRITES.labels(self._service, self._spec.name, "error").inc()
            logger.error("projection.write.failed", exc_info=True)
            raise

    def delete(self, entity_id: str) -> None:
        self._client.delete(self._spec.key(entity_id))

    def iter_keys(self) -> Iterator[str]:
        yield from self._client.scan_iter(match=self._spec.scan_pattern())

    def clear(self) -> int:
        removed = 0
        for key in self.iter_keys():
            self._client.delete(key)
            removed += 1
        return removed
