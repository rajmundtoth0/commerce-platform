"""auth-api: registration, login, token refresh, role-gated access."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_register_login_me_flow(auth_client: AsyncClient) -> None:
    reg = await auth_client.post(
        "/auth/register",
        json={"email": "c@example.com", "full_name": "Cust", "password": "password123"},
    )
    assert reg.status_code == 201, reg.text
    assert reg.json()["role"] == "customer"

    login = await auth_client.post(
        "/auth/login", json={"email": "c@example.com", "password": "password123"}
    )
    assert login.status_code == 200
    tokens = login.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    me = await auth_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "c@example.com"


async def test_refresh_issues_new_pair(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/auth/register",
        json={"email": "r@example.com", "full_name": "R", "password": "password123"},
    )
    tokens = (
        await auth_client.post(
            "/auth/login", json={"email": "r@example.com", "password": "password123"}
        )
    ).json()
    refreshed = await auth_client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]


async def test_bad_password_is_401(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/auth/register",
        json={"email": "x@example.com", "full_name": "X", "password": "password123"},
    )
    resp = await auth_client.post(
        "/auth/login", json={"email": "x@example.com", "password": "wrong"}
    )
    assert resp.status_code == 401


async def test_customer_cannot_list_users(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/auth/register",
        json={"email": "cust@example.com", "full_name": "C", "password": "password123"},
    )
    tokens = (
        await auth_client.post(
            "/auth/login", json={"email": "cust@example.com", "password": "password123"}
        )
    ).json()
    resp = await auth_client.get(
        "/users", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 403


async def test_seeded_admin_can_list_users(auth_client: AsyncClient) -> None:
    # The seed admin is created on startup; log in as that admin.
    login = await auth_client.post(
        "/auth/login", json={"email": "admin@example.com", "password": "admin12345"}
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    resp = await auth_client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert any(u["role"] == "admin" for u in resp.json())


async def test_health_and_ready(auth_client: AsyncClient) -> None:
    assert (await auth_client.get("/health")).status_code == 200
    ready = await auth_client.get("/ready")
    assert ready.json()["checks"]["postgres"] == "ok"
