"""Shared platform library for all commerce-platform services.

This package carries the cross-cutting concerns every service needs — config,
structured logging, telemetry, the Valkey client, the versioned-projection
contract, auth, the Celery app, and the ops endpoints — so that each service
stays small and focused on its own domain. Importing from `platform` is how the
services agree on the same contracts (projection keys, log fields, auth tokens).
"""

__version__ = "0.2.0"
