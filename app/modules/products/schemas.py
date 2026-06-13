"""Products API schemas and the product projection payload."""

from __future__ import annotations

from pydantic import Field

from app.shared.dto import APIModel


class ProductCreate(APIModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)
    active: bool = True


class ProductUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    active: bool | None = None


class ProductRead(APIModel):
    """Authoritative representation, served from Postgres."""

    id: str
    sku: str
    name: str
    description: str
    active: bool


class ProductProjection(APIModel):
    """Read-model payload cached under dk:product:v1:{id}.

    This shape is a contract for read consumers. Changing it requires bumping
    ProductProjectionWriter.schema_version.
    """

    id: str
    sku: str
    name: str
    description: str
    active: bool
