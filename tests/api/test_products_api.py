"""Product API tests, including the projection-backed read path."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.util import API_PREFIX as API

pytestmark = pytest.mark.asyncio


async def _create(client: AsyncClient, sku: str = "SKU-1") -> dict:
    resp = await client.post(
        f"{API}/products",
        json={"sku": sku, "name": "Widget", "description": "A widget"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_and_get_reads_from_projection(client: AsyncClient) -> None:
    created = await _create(client)
    product_id = created["id"]

    # GET reads the projection that the create event populated.
    resp = await client.get(f"{API}/products/{product_id}")
    assert resp.status_code == 200
    assert resp.json() == {
        "id": product_id,
        "sku": "SKU-1",
        "name": "Widget",
        "description": "A widget",
        "active": True,
    }


async def test_duplicate_sku_conflicts(client: AsyncClient) -> None:
    await _create(client, sku="DUP")
    resp = await client.post(f"{API}/products", json={"sku": "DUP", "name": "Other"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "conflict"


async def test_get_missing_returns_404(client: AsyncClient) -> None:
    resp = await client.get(f"{API}/products/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


async def test_update_refreshes_projection(client: AsyncClient) -> None:
    product_id = (await _create(client))["id"]
    resp = await client.patch(f"{API}/products/{product_id}", json={"name": "Renamed"})
    assert resp.status_code == 200

    cached = await client.get(f"{API}/products/{product_id}")
    assert cached.json()["name"] == "Renamed"


async def test_delete_removes_projection(client: AsyncClient) -> None:
    product_id = (await _create(client))["id"]
    assert (await client.delete(f"{API}/products/{product_id}")).status_code == 204
    assert (await client.get(f"{API}/products/{product_id}")).status_code == 404


async def test_list_pagination_envelope(client: AsyncClient) -> None:
    await _create(client, "A")
    await _create(client, "B")
    resp = await client.get(f"{API}/products", params={"limit": 1, "offset": 0})
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 1
    assert body["limit"] == 1


async def test_invalid_payload_returns_422(client: AsyncClient) -> None:
    resp = await client.post(f"{API}/products", json={"name": "no sku"})
    assert resp.status_code == 422
