"""Model aggregator.

Importing this module imports every ORM model, which is what populates
``Base.metadata``. Alembic's env and the test fixtures import from here so the
full schema is always registered in one place.
"""

from __future__ import annotations

from app.core.database import Base
from app.modules.cart.models import Cart, CartItem
from app.modules.orders.models import Order, OrderItem
from app.modules.pricing.models import ProductPrice
from app.modules.products.models import Product
from app.modules.users.models import User

__all__ = [
    "Base",
    "Cart",
    "CartItem",
    "Order",
    "OrderItem",
    "Product",
    "ProductPrice",
    "User",
]
