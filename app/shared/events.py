"""A tiny in-process, typed event bus.

This is the seam between the *write model* and the *read projections*. When a
service mutates authoritative state it publishes a domain event; projection
writers subscribe to those events and update Redis. The bus is intentionally
minimal — no broker, no retries — because projections are always rebuildable
from Postgres (see app/cli). It exists to make the write→projection flow
explicit rather than hidden inside service methods.

Events carry a self-contained snapshot of what changed so handlers never need to
re-read the database. The same snapshot shape is produced by the full-rebuild
job, so the event path and the rebuild path share one projection builder.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Event:
    """Base class for domain events."""


# --- Product domain events ------------------------------------------------
@dataclass(frozen=True, slots=True)
class ProductUpserted(Event):
    product_id: str
    sku: str
    name: str
    description: str
    active: bool


@dataclass(frozen=True, slots=True)
class ProductDeleted(Event):
    product_id: str


# --- Pricing domain events ------------------------------------------------
@dataclass(frozen=True, slots=True)
class PriceUpserted(Event):
    product_id: str
    currency: str
    amount_minor: int  # integer minor units (cents) — never floats for money


@dataclass(frozen=True, slots=True)
class PriceDeleted(Event):
    product_id: str


E = TypeVar("E", bound=Event)
Handler = Callable[[E], Awaitable[None]]


class EventBus:
    """Subscribe handlers per event type and publish events to them.

    Handlers run sequentially and their failures are logged but do not abort the
    publishing call: a projection write failing must be *visible* (logged +
    metric) but must not roll back the authoritative write that already
    committed. Drift is repaired by the rebuild job.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[Handler[Event]]] = defaultdict(list)

    def subscribe(self, event_type: type[E], handler: Handler[E]) -> None:
        self._handlers[event_type].append(handler)  # type: ignore[arg-type]

    async def publish(self, event: Event) -> None:
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception:  # failures must be visible, not fatal.
                logger.error(
                    "event.handler.failed",
                    event_type=type(event).__name__,
                    handler=getattr(handler, "__qualname__", repr(handler)),
                    exc_info=True,
                )

    async def publish_all(self, events: list[Event]) -> None:
        await asyncio.gather(*(self.publish(e) for e in events))


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the process-wide event bus singleton."""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def reset_event_bus() -> None:
    """Drop all subscriptions (used by tests for isolation)."""
    global _bus
    _bus = None
