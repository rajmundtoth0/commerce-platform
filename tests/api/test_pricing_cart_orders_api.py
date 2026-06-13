"""End-to-end flow: product -> price -> cart -> checkout."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.util import API_PREFIX as API

pytestmark = pytest.mark.asyncio


async def _product(client: AsyncClient, sku: str, price_minor: int) -> str:
    pid = (await client.post(f"{API}/products", json={"sku": sku, "name": sku})).json()["id"]
    resp = await client.put(
        f"{API}/products/{pid}/price", json={"currency": "USD", "amount_minor": price_minor}
    )
    assert resp.status_code == 200, resp.text
    return pid


async def _user(client: AsyncClient, email: str) -> str:
    resp = await client.post(f"{API}/users", json={"email": email, "full_name": "Tester"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_price_read_from_projection(client: AsyncClient) -> None:
    pid = await _product(client, "P1", 1500)
    resp = await client.get(f"{API}/products/{pid}/price")
    assert resp.status_code == 200
    assert resp.json() == {"product_id": pid, "currency": "USD", "amount_minor": 1500}


async def test_cart_view_uses_projections_and_totals(client: AsyncClient) -> None:
    pid = await _product(client, "P2", 1000)
    uid = await _user(client, "a@example.com")

    resp = await client.post(
        f"{API}/users/{uid}/cart/items", json={"product_id": pid, "quantity": 3}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["total_amount_minor"] == 3000
    assert body["currency"] == "USD"
    assert body["has_unpriced_items"] is False
    assert body["items"][0]["name"] == "P2"


async def test_checkout_creates_order_and_clears_cart(client: AsyncClient) -> None:
    pid = await _product(client, "P3", 2500)
    uid = await _user(client, "b@example.com")
    await client.post(f"{API}/users/{uid}/cart/items", json={"product_id": pid, "quantity": 2})

    resp = await client.post(f"{API}/users/{uid}/orders")
    assert resp.status_code == 201, resp.text
    order = resp.json()
    assert order["total_amount_minor"] == 5000
    assert order["items"][0]["unit_amount_minor"] == 2500
    assert order["status"] == "created"

    # Cart is emptied after checkout.
    cart = await client.get(f"{API}/users/{uid}/cart")
    assert cart.json()["items"] == []


async def test_checkout_empty_cart_conflicts(client: AsyncClient) -> None:
    uid = await _user(client, "c@example.com")
    resp = await client.post(f"{API}/users/{uid}/orders")
    assert resp.status_code == 409


async def test_checkout_unpriced_item_conflicts(client: AsyncClient) -> None:
    # Product with no price set -> cart line is unpriced -> checkout refused.
    pid = (await client.post(f"{API}/products", json={"sku": "NP", "name": "NoPrice"})).json()["id"]
    uid = await _user(client, "d@example.com")
    await client.post(f"{API}/users/{uid}/cart/items", json={"product_id": pid, "quantity": 1})

    resp = await client.post(f"{API}/users/{uid}/orders")
    assert resp.status_code == 409
    assert "price" in resp.json()["message"].lower()
