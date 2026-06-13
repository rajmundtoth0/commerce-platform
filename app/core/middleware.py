"""HTTP middleware: request correlation ids and Prometheus metrics."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger, request_id_ctx, trace_id_ctx
from app.core.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS
from app.core.telemetry import current_trace_id

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

Dispatch = Callable[[Request], Awaitable[Response]]


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a request id (and the active trace id) for the duration of a request.

    The request id is taken from the inbound X-Request-ID header when present so
    correlation survives across services, otherwise one is generated. Both ids
    are echoed back on the response and bound into the logging context.
    """

    async def dispatch(self, request: Request, call_next: Dispatch) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        rid_token = request_id_ctx.set(request_id)
        tid_token = trace_id_ctx.set(current_trace_id())
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(rid_token)
            trace_id_ctx.reset(tid_token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request counts and latency.

    We label by the matched route template (e.g. /products/{product_id}) rather
    than the raw path, so high-cardinality ids do not explode the metric space.
    """

    async def dispatch(self, request: Request, call_next: Dispatch) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        method = request.method

        HTTP_REQUESTS.labels(method=method, path=path, status=response.status_code).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(elapsed)
        return response
