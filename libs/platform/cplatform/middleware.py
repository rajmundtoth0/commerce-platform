"""HTTP middleware: request-context binding + Prometheus metrics."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from cplatform.logging import bind_context, clear_context
from cplatform.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS
from cplatform.telemetry import current_trace_id

REQUEST_ID_HEADER = "X-Request-ID"
Dispatch = Callable[[Request], Awaitable[Response]]


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind service/request_id/trace_id for the duration of each request."""

    def __init__(self, app: object, *, service_name: str) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._service = service_name

    async def dispatch(self, request: Request, call_next: Dispatch) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        clear_context()
        bind_context(service=self._service, request_id=request_id, trace_id=current_trace_id())
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request count + latency labeled by route template (low cardinality)."""

    def __init__(self, app: object, *, service_name: str) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._service = service_name

    async def dispatch(self, request: Request, call_next: Dispatch) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS.labels(self._service, request.method, path, response.status_code).inc()
        HTTP_REQUEST_DURATION.labels(self._service, request.method, path).observe(elapsed)
        return response
