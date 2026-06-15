"""Minimal SQLAdmin UI for the authoritative catalog (mounted at /admin/db).

This demonstrates a service-owned admin UI over the source-of-truth tables. The
authentication backend is intentionally trivial — it accepts the single seed
admin credential from settings — since the point is to show an admin surface,
not a full IAM. Real auth is the JWT-gated HTTP API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from backoffice_api.models import Product, ProductPrice
from backoffice_api.settings import BackofficeSettings

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine


class AdminAuth(AuthenticationBackend):
    def __init__(self, settings: BackofficeSettings) -> None:
        super().__init__(secret_key=settings.jwt_secret)
        self._email = settings.seed_admin_email
        self._password = settings.seed_admin_password

    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = str(form.get("username", ""))
        password = str(form.get("password", ""))
        if email == self._email and password == self._password:
            request.session.update({"admin": email})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return bool(request.session.get("admin"))


class ProductAdmin(ModelView, model=Product):
    column_list = [Product.id, Product.sku, Product.name, Product.active, Product.featured]
    column_searchable_list = [Product.sku, Product.name]
    name = "Product"
    name_plural = "Products"


class ProductPriceAdmin(ModelView, model=ProductPrice):
    column_list = [
        ProductPrice.product_id,
        ProductPrice.currency,
        ProductPrice.amount_minor,
    ]
    name = "Price"
    name_plural = "Prices"


def mount_admin(app: FastAPI, engine: AsyncEngine, settings: BackofficeSettings) -> Admin:
    admin = Admin(
        app,
        engine,
        base_url="/admin/db",
        authentication_backend=AdminAuth(settings),
    )
    admin.add_view(ProductAdmin)
    admin.add_view(ProductPriceAdmin)
    return admin
