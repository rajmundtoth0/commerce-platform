from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, MetaData, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from cplatform.db import NAMING_CONVENTION, TimestampMixin


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def new_id() -> str:
    return uuid.uuid4().hex


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ProductPrice(Base, TimestampMixin):
    __tablename__ = "product_prices"

    product_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (CheckConstraint("amount_minor >= 0", name="amount_minor_non_negative"),)
