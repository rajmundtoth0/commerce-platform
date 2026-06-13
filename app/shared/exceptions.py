"""Domain exception hierarchy.

Services raise these domain-level errors; a single FastAPI exception handler
(app/main.py) maps them to HTTP responses. Modules therefore stay free of HTTP
concerns and remain reusable from CLIs, jobs, and tests.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain errors.

    `code` is a stable, machine-readable string that becomes part of the API
    error contract; `status_code` is the HTTP status the handler should emit.
    """

    code: str = "domain_error"
    status_code: int = 400

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(DomainError):
    code = "not_found"
    status_code = 404


class ConflictError(DomainError):
    """A uniqueness or state conflict (e.g. duplicate SKU, empty cart checkout)."""

    code = "conflict"
    status_code = 409


class ValidationError(DomainError):
    """Business-rule validation failure (distinct from request-schema validation)."""

    code = "validation_error"
    status_code = 422


class ProjectionError(DomainError):
    """A read projection could not be built or read consistently."""

    code = "projection_error"
    status_code = 503
