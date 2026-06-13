"""Orders write model.

An order snapshots prices at checkout time into its line items, so later price
changes never alter historical orders. Orders are authoritative and are never
served from a projection.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.modules.products.models import new_id


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str] = mapped_column(String(32), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
