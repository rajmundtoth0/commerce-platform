"""Pricing write model.

Money is stored as integer minor units (e.g. cents) plus an ISO-4217 currency
code. Floats are never used for monetary amounts.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class ProductPrice(Base, TimestampMixin):
    __tablename__ = "product_prices"
    __table_args__ = (CheckConstraint("amount_minor >= 0", name="amount_minor_non_negative"),)

    # One current price per product; product_id is the natural primary key.
    product_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
