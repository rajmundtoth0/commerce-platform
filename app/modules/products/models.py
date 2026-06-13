"""Products write model (authoritative, in Postgres)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


def new_id() -> str:
    """Application-generated primary key (portable across Postgres/SQLite)."""
    return uuid.uuid4().hex


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
