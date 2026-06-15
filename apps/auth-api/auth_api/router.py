from __future__ import annotations

from fastapi import APIRouter, status

from auth_api.deps import AdminUser, CurrentUser, ServiceDep
from auth_api.schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenPair, UserRead

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


@auth_router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, service: ServiceDep) -> UserRead:
    return UserRead.model_validate(await service.register(data))


@auth_router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest, service: ServiceDep) -> TokenPair:
    user = await service.authenticate(str(data.email), data.password)
    return service.issue_pair(user)


@auth_router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest, service: ServiceDep) -> TokenPair:
    return await service.refresh(data.refresh_token)


@auth_router.get("/me", response_model=UserRead)
async def me(claims: CurrentUser, service: ServiceDep) -> UserRead:
    return UserRead.model_validate(await service.get(claims.sub))


# Admin-only user listing demonstrates role-gated access within the service.
@users_router.get("", response_model=list[UserRead])
async def list_users(_admin: AdminUser, service: ServiceDep) -> list[UserRead]:
    return [UserRead.model_validate(u) for u in await service.list_users()]
