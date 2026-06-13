"""Cart write model.

A user has at most one open cart. Cart contents are authoritative in Postgres;
the *view* of a cart (names, prices, totals) is assembled from the product and
product-price read projections — see service.py.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.modules.products.models import new_id


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )


class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "product_id", name="cart_product_unique"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    cart_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("carts.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("products.id", ondelete="CASCADE")
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
