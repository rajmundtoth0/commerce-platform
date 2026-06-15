from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    active: bool = True
    featured: bool = False


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    active: bool | None = None
    featured: bool | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sku: str
    name: str
    description: str
    active: bool
    featured: bool


class ProductList(BaseModel):
    items: list[ProductRead]
    total: int
    limit: int
    offset: int


class PriceUpsert(BaseModel):
    currency: str = Field(default="USD", min_length=3, max_length=3)
    amount_minor: int = Field(ge=0)


class PriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    currency: str
    amount_minor: int
