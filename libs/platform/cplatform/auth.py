"""Authentication primitives shared across services.

auth-api ISSUES tokens; every other service VERIFIES them with the same shared
secret and exposes the same FastAPI dependencies. This is the auth boundary: a
service trusts a request because the JWT validates, not because of where it came
from.

Kept deliberately simple (symmetric HS256, two roles) — the point is to
demonstrate service-owned identity and auth boundaries, not to build a full IAM.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from cplatform.errors import AuthError, ForbiddenError

Role = Literal["customer", "admin"]
TokenType = Literal["access", "refresh"]


# --- Password hashing -----------------------------------------------------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


# --- Tokens ---------------------------------------------------------------
class TokenClaims(BaseModel):
    sub: str  # user id
    email: str
    role: Role
    type: TokenType
    exp: int
    iat: int


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


def issue_token(
    *,
    user_id: str,
    email: str,
    role: Role,
    token_type: TokenType,
    secret: str,
    algorithm: str,
    ttl_seconds: int,
) -> str:
    issued = _now()
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": token_type,
        "iat": int(issued.timestamp()),
        "exp": int((issued + dt.timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, *, secret: str, algorithm: str) -> TokenClaims:
    try:
        raw = jwt.decode(token, secret, algorithms=[algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid token") from exc
    return TokenClaims.model_validate(raw)


# --- FastAPI dependencies -------------------------------------------------
# Services construct these with their own settings via `build_auth_deps`.
_bearer = HTTPBearer(auto_error=False)


class AuthDeps:
    """Factory bound to a service's JWT settings."""

    def __init__(self, *, secret: str, algorithm: str) -> None:
        self._secret = secret
        self._algorithm = algorithm

    async def current_claims(
        self, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
    ) -> TokenClaims:
        if creds is None:
            raise AuthError("Missing bearer token")
        claims = decode_token(creds.credentials, secret=self._secret, algorithm=self._algorithm)
        if claims.type != "access":
            raise AuthError("Access token required")
        return claims

    def require_role(self, *roles: Role):  # type: ignore[no-untyped-def]
        # NOTE: use a default-value Depends (not an Annotated dependency) here.
        # With `from __future__ import annotations` the Annotated form is
        # stringized and FastAPI cannot resolve the closure's `self`, so it would
        # mistake `claims` for a query param. A default Depends is a real object.
        async def _dep(claims: TokenClaims = Depends(self.current_claims)) -> TokenClaims:
            if claims.role not in roles:
                raise ForbiddenError(
                    "Insufficient role", details={"required": list(roles), "actual": claims.role}
                )
            return claims

        return _dep
