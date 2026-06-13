"""Common FastAPI dependencies shared by module routers.

Routers compose these into per-domain service/projection dependencies. Keeping
the primitives here avoids each module re-declaring how to obtain a session,
the event bus, or the Redis client.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.redis import RedisClient, get_redis
from app.shared.events import EventBus, get_event_bus

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[RedisClient, Depends(get_redis)]
BusDep = Annotated[EventBus, Depends(get_event_bus)]
