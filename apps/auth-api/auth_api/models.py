from __future__ import annotations

import uuid

from sqlalchemy import Boolean, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from cplatform.db import NAMING_CONVENTION, TimestampMixin


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def new_id() -> str:
    return uuid.uuid4().hex


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="customer")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
