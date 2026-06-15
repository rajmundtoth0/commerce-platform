from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=32)
    product_name: str = Field(min_length=1, max_length=255)
    quantity: int = Field(ge=1)
    unit_amount_minor: int = Field(ge=0)


class OrderCreate(BaseModel):
    currency: str = Field(min_length=3, max_length=3)
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    product_name: str
    quantity: int
    unit_amount_minor: int


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    status: str
    currency: str
    total_amount_minor: int
    items: list[OrderItemRead]
