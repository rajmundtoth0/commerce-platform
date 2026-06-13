"""Users service — straightforward Postgres CRUD.

This module deliberately has no Redis projection: user records are read by id in
admin/auth flows, not on hot public read paths, so adding a projection would be
unnecessary abstraction. Boundaries stay explicit — projections are added only
where a read path needs them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserUpdate
from app.shared.exceptions import ConflictError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: UserCreate) -> User:
        user = User(email=str(data.email), full_name=data.full_name)
        self._session.add(user)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                f"User with email '{data.email}' already exists",
                details={"email": str(data.email)},
            ) from exc
        return user

    async def get(self, user_id: str) -> User:
        user = await self._session.get(User, user_id)
        if user is None:
            raise NotFoundError(f"User '{user_id}' not found", details={"id": user_id})
        return user

    async def list(self, *, limit: int, offset: int) -> tuple[list[User], int]:
        total = await self._session.scalar(select(func.count()).select_from(User)) or 0
        rows = await self._session.scalars(
            select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
        return list(rows), total

    async def update(self, user_id: str, data: UserUpdate) -> User:
        user = await self.get(user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await self._session.flush()
        return user

    async def delete(self, user_id: str) -> None:
        user = await self.get(user_id)
        await self._session.delete(user)
        await self._session.flush()
