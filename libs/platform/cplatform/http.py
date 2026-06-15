"""Typed service-to-service HTTP client.

Used where one service calls another over HTTP (e.g. webshop-api -> orders-api).
It forwards the caller's bearer token and the request id so auth and tracing
propagate across the service boundary. Failures surface as `UpstreamError` so a
dependency outage is a clean 502, not a stack trace.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from cplatform.errors import DomainError, UpstreamError
from cplatform.logging import get_logger

logger = get_logger("http")


class ServiceClient:
    """Thin wrapper over httpx.AsyncClient for calling a sibling service."""

    def __init__(self, base_url: str, *, name: str, timeout: float = 5.0) -> None:
        self._name = name
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    def _headers(self, bearer: str | None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        request_id = structlog.contextvars.get_contextvars().get("request_id")
        if request_id:
            headers["X-Request-ID"] = str(request_id)
        return headers

    async def request(
        self,
        method: str,
        path: str,
        *,
        bearer: str | None = None,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        try:
            resp = await self._client.request(
                method, path, json=json, params=params, headers=self._headers(bearer)
            )
        except httpx.HTTPError as exc:
            logger.warning("upstream.unreachable", service=self._name, path=path, error=str(exc))
            raise UpstreamError(f"{self._name} is unreachable") from exc

        if resp.status_code >= 400:
            # Re-raise the upstream's domain error shape when present, preserving
            # its status code and machine-readable code.
            body = _safe_json(resp)
            if isinstance(body, dict):
                code = str(body.get("code", "upstream_error"))
                message = str(body.get("message", resp.text))
            else:
                code, message = "upstream_error", resp.text
            raise _mapped_error(resp.status_code, code, message)
        return _safe_json(resp)

    async def aclose(self) -> None:
        await self._client.aclose()


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text


def _mapped_error(status: int, code: str, message: str) -> DomainError:
    err = DomainError(message)
    err.code = code
    err.status_code = status
    return err
