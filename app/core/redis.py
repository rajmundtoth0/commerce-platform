"""Async Redis client used as the versioned read-model / projection cache.

Redis is *never* the source of truth — it holds projections that can be fully
rebuilt from Postgres at any time (see app/cli and modules/*/projections.py).
"""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings

# Single alias for the async client. We always run with decode_responses=True,
# so values come back as `str`.
type RedisClient = Redis

_redis: RedisClient | None = None


def get_redis() -> RedisClient:
    """Return the lazily-created process-wide async Redis client."""
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


def set_redis(client: RedisClient) -> None:
    """Override the client (used by tests to inject fakeredis)."""
    global _redis
    _redis = client


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None
