"""Users API schemas."""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.shared.dto import APIModel


class UserCreate(APIModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)


class UserUpdate(APIModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None


class UserRead(APIModel):
    id: str
    email: EmailStr
    full_name: str
    active: bool
