from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from cplatform.db import Database
from cplatform.errors import AuthError, ForbiddenError
from status_api.service import StatusService
from status_api.settings import settings

_settings = settings()
database = Database(_settings.postgres_dsn, echo=_settings.db_echo)
_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(database.session_dependency)]


def get_service(session: SessionDep) -> StatusService:
    return StatusService(session, recent_limit=_settings.recent_incident_limit)


ServiceDep = Annotated[StatusService, Depends(get_service)]


async def require_ops_token(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Guard write endpoints with the single internal ops token.

    Missing token -> 401; wrong token -> 403. Constant-time comparison; the token
    is never logged or returned.
    """
    if creds is None:
        raise AuthError("Missing bearer token")
    if not secrets.compare_digest(creds.credentials, _settings.ops_status_token):
        raise ForbiddenError("Invalid ops token")


OpsToken = Annotated[None, Depends(require_ops_token)]
