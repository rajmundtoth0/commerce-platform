"""Ops endpoints and basic user CRUD."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.util import API_PREFIX as API

pytestmark = pytest.mark.asyncio


async def test_health_is_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_ready_checks_dependencies(client: AsyncClient) -> None:
    resp = await client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["checks"]["postgres"] == "ok"
    assert body["checks"]["redis"] == "ok"


async def test_metrics_exposes_prometheus(client: AsyncClient) -> None:
    await client.get("/health")  # generate at least one metric sample
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text


async def test_request_id_is_echoed(client: AsyncClient) -> None:
    resp = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert resp.headers["X-Request-ID"] == "abc-123"


async def test_user_crud(client: AsyncClient) -> None:
    created = await client.post(
        f"{API}/users", json={"email": "u@example.com", "full_name": "User One"}
    )
    assert created.status_code == 201
    uid = created.json()["id"]

    assert (await client.get(f"{API}/users/{uid}")).json()["email"] == "u@example.com"

    patched = await client.patch(f"{API}/users/{uid}", json={"active": False})
    assert patched.json()["active"] is False

    assert (await client.delete(f"{API}/users/{uid}")).status_code == 204
    assert (await client.get(f"{API}/users/{uid}")).status_code == 404


async def test_duplicate_email_conflicts(client: AsyncClient) -> None:
    await client.post(f"{API}/users", json={"email": "dup@example.com", "full_name": "A"})
    resp = await client.post(f"{API}/users", json={"email": "dup@example.com", "full_name": "B"})
    assert resp.status_code == 409
