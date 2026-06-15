from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cplatform.auth import AuthDeps, TokenClaims
from cplatform.db import Database
from orders_api.service import OrderService
from orders_api.settings import settings

_settings = settings()
database = Database(_settings.postgres_dsn, echo=_settings.db_echo)
auth_deps = AuthDeps(secret=_settings.jwt_secret, algorithm=_settings.jwt_algorithm)

SessionDep = Annotated[AsyncSession, Depends(database.session_dependency)]


def get_service(session: SessionDep) -> OrderService:
    return OrderService(session)


ServiceDep = Annotated[OrderService, Depends(get_service)]
CurrentUser = Annotated[TokenClaims, Depends(auth_deps.current_claims)]
AdminUser = Annotated[TokenClaims, Depends(auth_deps.require_role("admin"))]
