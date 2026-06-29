"""Health check specs + a small runner.

A check is either an HTTP probe (GET a /ready or /health URL, expect a status) or
a TCP connect probe (for dependencies without an HTTP endpoint, e.g. Postgres,
Valkey). The runner is deliberately tiny: short timeouts, no retries, every check
maps to one component status. `map_outcome_to_status` is a pure function so the
mapping rules are trivially testable.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

import httpx
from pydantic import BaseModel

CheckKind = Literal["http", "tcp"]
ComponentStatus = Literal["operational", "degraded", "down", "maintenance", "unknown"]
OutcomeKind = Literal["ok", "bad_status", "timeout", "conn_error", "unknown"]


class CheckSpec(BaseModel):
    """One configured health check (overridable via the STATUS_CHECKS env / Helm)."""

    id: str
    name: str
    kind: CheckKind = "http"
    description: str = ""
    url: str | None = None
    host: str | None = None
    port: int | None = None
    expected_status: int = 200


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    kind: OutcomeKind
    http_status: int | None = None
    error: str | None = None


def map_outcome_to_status(outcome: CheckOutcome) -> ComponentStatus:
    """Map a raw probe outcome to a component status (the documented rules)."""
    match outcome.kind:
        case "ok":
            return "operational"
        case "bad_status":
            return "degraded"  # responded, but not the expected status
        case "timeout" | "conn_error":
            return "down"
        case _:
            return "unknown"


async def run_check(
    spec: CheckSpec, *, client: httpx.AsyncClient, timeout_s: float = 2.0
) -> CheckOutcome:
    """Execute one check. Never raises — failures become CheckOutcomes."""
    try:
        if spec.kind == "tcp":
            if not spec.host or not spec.port:
                return CheckOutcome("unknown", error="tcp check missing host/port")
            fut = asyncio.open_connection(spec.host, spec.port)
            reader_writer = await asyncio.wait_for(fut, timeout=timeout_s)
            reader_writer[1].close()
            return CheckOutcome("ok")
        # http
        if not spec.url:
            return CheckOutcome("unknown", error="http check missing url")
        resp = await client.get(spec.url, timeout=timeout_s)
        if resp.status_code == spec.expected_status:
            return CheckOutcome("ok", http_status=resp.status_code)
        return CheckOutcome("bad_status", http_status=resp.status_code)
    except (TimeoutError, httpx.TimeoutException):
        return CheckOutcome("timeout", error="timeout")
    except (OSError, httpx.HTTPError) as exc:
        return CheckOutcome("conn_error", error=str(exc)[:300])


# Default checks (compose/k8s service DNS). Override via STATUS_CHECKS (JSON) or
# Helm `opsStatus.statusChecks`.
DEFAULT_CHECKS: list[CheckSpec] = [
    CheckSpec(id="webshop-api", name="Webshop API", url="http://webshop-api:8000/ready"),
    CheckSpec(id="orders-api", name="Orders API", url="http://orders-api:8003/ready"),
    CheckSpec(id="auth-api", name="Auth API", url="http://auth-api:8002/ready"),
    CheckSpec(id="backoffice-api", name="Backoffice API", url="http://backoffice-api:8001/ready"),
    CheckSpec(id="worker", name="Worker", url="http://worker:9100/"),
    CheckSpec(id="postgres", name="Postgres", kind="tcp", host="postgres", port=5432),
    CheckSpec(id="valkey", name="Valkey", kind="tcp", host="valkey", port=6380),
    CheckSpec(id="elasticsearch", name="Elasticsearch", url="http://elasticsearch:9200"),
]
