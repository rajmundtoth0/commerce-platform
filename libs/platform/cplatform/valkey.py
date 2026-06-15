"""Valkey clients.

Valkey is Redis-compatible, so we use the `redis` client library against it. We
expose both an async client (for API services reading projections) and a sync
client (for the Celery worker writing projections). Connections are created
lazily and cached per URL.
"""

from __future__ import annotations

from redis import Redis as SyncRedis
from redis.asyncio import Redis as AsyncRedis

type AsyncValkey = AsyncRedis
type SyncValkey = SyncRedis

_async_clients: dict[str, AsyncValkey] = {}
_sync_clients: dict[str, SyncValkey] = {}


def get_async_valkey(url: str) -> AsyncValkey:
    client = _async_clients.get(url)
    if client is None:
        client = AsyncRedis.from_url(url, encoding="utf-8", decode_responses=True)
        _async_clients[url] = client
    return client


def get_sync_valkey(url: str) -> SyncValkey:
    client = _sync_clients.get(url)
    if client is None:
        client = SyncRedis.from_url(url, encoding="utf-8", decode_responses=True)
        _sync_clients[url] = client
    return client


def set_async_valkey(url: str, client: AsyncValkey) -> None:
    """Override a cached async client (used by tests to inject fakeredis)."""
    _async_clients[url] = client


def set_sync_valkey(url: str, client: SyncValkey) -> None:
    _sync_clients[url] = client


async def close_async_valkey() -> None:
    for client in _async_clients.values():
        await client.aclose()
    _async_clients.clear()
