from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from auth_api.models import User
from auth_api.schemas import RegisterRequest, TokenPair
from auth_api.settings import AuthSettings
from cplatform.auth import (
    Role,
    TokenClaims,
    decode_token,
    hash_password,
    issue_token,
    verify_password,
)
from cplatform.errors import AuthError, ConflictError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AuthService:
    def __init__(self, session: AsyncSession, settings: AuthSettings) -> None:
        self._session = session
        self._settings = settings

    # --- user management -------------------------------------------------
    async def register(self, data: RegisterRequest, *, role: Role = "customer") -> User:
        user = User(
            email=str(data.email),
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            role=role,
        )
        self._session.add(user)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                f"Email '{data.email}' is already registered", details={"email": str(data.email)}
            ) from exc
        return user

    async def get(self, user_id: str) -> User:
        user = await self._session.get(User, user_id)
        if user is None:
            raise NotFoundError(f"User '{user_id}' not found", details={"id": user_id})
        return user

    async def list_users(self) -> list[User]:
        return list(await self._session.scalars(select(User).order_by(User.created_at.desc())))

    # --- authentication --------------------------------------------------
    async def _by_email(self, email: str) -> User | None:
        result: User | None = await self._session.scalar(select(User).where(User.email == email))
        return result

    async def authenticate(self, email: str, password: str) -> User:
        user = await self._by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise AuthError("Invalid email or password")
        if not user.active:
            raise AuthError("Account is disabled")
        return user

    def issue_pair(self, user: User) -> TokenPair:
        s = self._settings
        role: Role = "admin" if user.role == "admin" else "customer"
        access = issue_token(
            user_id=user.id,
            email=user.email,
            role=role,
            token_type="access",
            secret=s.jwt_secret,
            algorithm=s.jwt_algorithm,
            ttl_seconds=s.access_token_ttl_seconds,
        )
        refresh = issue_token(
            user_id=user.id,
            email=user.email,
            role=role,
            token_type="refresh",
            secret=s.jwt_secret,
            algorithm=s.jwt_algorithm,
            ttl_seconds=s.refresh_token_ttl_seconds,
        )
        return TokenPair(access_token=access, refresh_token=refresh)

    async def refresh(self, refresh_token: str) -> TokenPair:
        claims: TokenClaims = decode_token(
            refresh_token, secret=self._settings.jwt_secret, algorithm=self._settings.jwt_algorithm
        )
        if claims.type != "refresh":
            raise AuthError("Refresh token required")
        user = await self.get(claims.sub)
        return self.issue_pair(user)
