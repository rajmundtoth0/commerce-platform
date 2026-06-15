"""backoffice-api: authoritative product/price CRUD, role gating, projections."""

from __future__ import annotations

import pytest
import pytest_asyncio
from backoffice_api.settings import settings
from httpx import ASGITransport, AsyncClient

from cplatform.auth import issue_token

pytestmark = pytest.mark.asyncio


def _token(role: str) -> str:
    s = settings()
    return issue_token(
        user_id=f"{role}-1",
        email=f"{role}@example.com",
        role=role,  # type: ignore[arg-type]
        token_type="access",
        secret=s.jwt_secret,
        algorithm=s.jwt_algorithm,
        ttl_seconds=3600,
    )


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token('admin')}"}


def _customer_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token('customer')}"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    from backoffice_api.deps import database
    from backoffice_api.main import app
    from backoffice_api.models import Base

    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://backoffice") as c:
        async with app.router.lifespan_context(app):
            yield c
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _create_product(client: AsyncClient, sku: str = "SKU-1") -> dict:
    resp = await client.post(
        "/products",
        json={"sku": sku, "name": "Widget", "description": "A widget"},
        headers=_admin_headers(),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_product(client: AsyncClient) -> None:
    body = await _create_product(client)
    assert body["sku"] == "SKU-1"
    assert body["active"] is True
    assert body["featured"] is False
    assert body["id"]


async def test_duplicate_sku_conflict(client: AsyncClient) -> None:
    await _create_product(client, sku="DUP")
    resp = await client.post(
        "/products",
        json={"sku": "DUP", "name": "Other"},
        headers=_admin_headers(),
    )
    assert resp.status_code == 409, resp.text


async def test_set_and_get_price(client: AsyncClient) -> None:
    product = await _create_product(client, sku="PRICED")
    pid = product["id"]

    put = await client.put(
        f"/products/{pid}/price",
        json={"currency": "USD", "amount_minor": 1999},
        headers=_admin_headers(),
    )
    assert put.status_code == 200, put.text
    assert put.json()["amount_minor"] == 1999

    got = await client.get(f"/products/{pid}/price", headers=_admin_headers())
    assert got.status_code == 200
    assert got.json()["currency"] == "USD"

    # Price on a missing product is a 404.
    missing = await client.put(
        "/products/does-not-exist/price",
        json={"amount_minor": 100},
        headers=_admin_headers(),
    )
    assert missing.status_code == 404


async def test_get_product(client: AsyncClient) -> None:
    product = await _create_product(client, sku="GET")
    got = await client.get(f"/products/{product['id']}", headers=_admin_headers())
    assert got.status_code == 200
    assert got.json()["sku"] == "GET"

    assert (await client.get("/products/nope", headers=_admin_headers())).status_code == 404


async def test_patch_featured_flag(client: AsyncClient) -> None:
    product = await _create_product(client, sku="PATCH")
    patched = await client.patch(
        f"/products/{product['id']}",
        json={"featured": True},
        headers=_admin_headers(),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["featured"] is True


async def test_list_paging(client: AsyncClient) -> None:
    for i in range(3):
        await _create_product(client, sku=f"LIST-{i}")
    resp = await client.get("/products?limit=2&offset=0", headers=_admin_headers())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["items"]) == 2


async def test_customer_forbidden_on_write(client: AsyncClient) -> None:
    resp = await client.post(
        "/products",
        json={"sku": "NOPE", "name": "X"},
        headers=_customer_headers(),
    )
    assert resp.status_code == 403, resp.text


async def test_rebuild_all_returns_202(client: AsyncClient) -> None:
    resp = await client.post("/admin/projections/rebuild", headers=_admin_headers())
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["enqueued"] is True
    assert body["task"]


async def test_list_projections(client: AsyncClient) -> None:
    resp = await client.get("/admin/projections", headers=_admin_headers())
    assert resp.status_code == 200, resp.text
    specs = resp.json()
    assert len(specs) == 2
    names = {s["name"] for s in specs}
    assert names == {"product", "product-price"}


async def test_delete_product(client: AsyncClient) -> None:
    product = await _create_product(client, sku="DEL")
    pid = product["id"]
    resp = await client.delete(f"/products/{pid}", headers=_admin_headers())
    assert resp.status_code == 204
    gone = await client.get(f"/products/{pid}", headers=_admin_headers())
    assert gone.status_code == 404


async def test_rebuild_builders_with_sync_session(client: AsyncClient) -> None:
    # Create authoritative data via the API, then read it back through the sync
    # rebuild builders the worker uses.
    product = await _create_product(client, sku="SYNC")
    pid = product["id"]
    await client.put(
        f"/products/{pid}/price",
        json={"currency": "EUR", "amount_minor": 500},
        headers=_admin_headers(),
    )

    from backoffice_api.deps import database
    from backoffice_api.rebuild import build_price, build_product
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from cplatform.sync_db import to_sync_dsn

    engine = create_engine(to_sync_dsn(database.dsn))
    with Session(engine) as session:
        proj = build_product(session, pid)
        assert proj is not None
        assert proj.sku == "SYNC"
        assert proj.featured is False

        price = build_price(session, pid)
        assert price is not None
        assert price.currency == "EUR"
        assert price.amount_minor == 500

        assert build_product(session, "missing") is None
        assert build_price(session, "missing") is None
    engine.dispose()
