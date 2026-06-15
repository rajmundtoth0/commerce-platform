from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backoffice_api.service import CatalogService
from backoffice_api.settings import settings
from cplatform.auth import AuthDeps, TokenClaims
from cplatform.db import Database

_settings = settings()
database = Database(_settings.postgres_dsn, echo=_settings.db_echo)
auth_deps = AuthDeps(secret=_settings.jwt_secret, algorithm=_settings.jwt_algorithm)

SessionDep = Annotated[AsyncSession, Depends(database.session_dependency)]


def get_service(session: SessionDep) -> CatalogService:
    return CatalogService(session)


ServiceDep = Annotated[CatalogService, Depends(get_service)]
AdminUser = Annotated[TokenClaims, Depends(auth_deps.require_role("admin"))]
