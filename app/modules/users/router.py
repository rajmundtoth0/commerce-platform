"""Users HTTP API (Postgres-backed, no projection)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.modules.users.schemas import UserCreate, UserRead, UserUpdate
from app.modules.users.service import UserService
from app.shared.deps import SessionDep
from app.shared.dto import Page

router = APIRouter(prefix="/users", tags=["users"])


def get_service(session: SessionDep) -> UserService:
    return UserService(session)


ServiceDep = Annotated[UserService, Depends(get_service)]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, service: ServiceDep) -> UserRead:
    return UserRead.model_validate(await service.create(data))


@router.get("", response_model=Page[UserRead])
async def list_users(
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[UserRead]:
    items, total = await service.list(limit=limit, offset=offset)
    return Page[UserRead](
        items=[UserRead.model_validate(u) for u in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: str, service: ServiceDep) -> UserRead:
    return UserRead.model_validate(await service.get(user_id))


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(user_id: str, data: UserUpdate, service: ServiceDep) -> UserRead:
    return UserRead.model_validate(await service.update(user_id, data))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, service: ServiceDep) -> Response:
    await service.delete(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
