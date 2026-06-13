"""Shared DTO/base schema types used across modules.

Keeping these tiny and explicit avoids a sprawling "common" layer. Every module
defines its own request/response schemas but reuses these primitives.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Base for all API-facing schemas.

    `from_attributes` lets us build responses directly from ORM objects, and
    `populate_by_name` allows alias-friendly field names.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class Page[T](APIModel):
    """A simple offset-paginated envelope."""

    items: list[T]
    total: int
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)


class ErrorResponse(APIModel):
    """Canonical error body returned for every handled error."""

    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)
    request_id: str | None = None
