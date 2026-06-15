from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth_api.service import AuthService
from auth_api.settings import settings
from cplatform.auth import AuthDeps, TokenClaims
from cplatform.db import Database

_settings = settings()
database = Database(_settings.postgres_dsn, echo=_settings.db_echo)
auth_deps = AuthDeps(secret=_settings.jwt_secret, algorithm=_settings.jwt_algorithm)

SessionDep = Annotated[AsyncSession, Depends(database.session_dependency)]


def get_service(session: SessionDep) -> AuthService:
    return AuthService(session, _settings)


ServiceDep = Annotated[AuthService, Depends(get_service)]
CurrentUser = Annotated[TokenClaims, Depends(auth_deps.current_claims)]
AdminUser = Annotated[TokenClaims, Depends(auth_deps.require_role("admin"))]
