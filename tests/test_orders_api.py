from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from orders_api.deps import database
from orders_api.main import app
from orders_api.models import Base
from orders_api.settings import settings

from cplatform.auth import issue_token
from cplatform.sync_db import SyncDatabase

pytestmark = pytest.mark.asyncio


def _token(*, user_id: str, role: str) -> str:
    s = settings()
    return issue_token(
        user_id=user_id,
        email=f"{user_id}@example.com",
        role=role,  # type: ignore[arg-type]
        token_type="access",
        secret=s.jwt_secret,
        algorithm=s.jwt_algorithm,
        ttl_seconds=3600,
    )


def _auth(*, user_id: str, role: str = "customer") -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id=user_id, role=role)}"}


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://orders") as ac:
        async with app.router.lifespan_context(app):
            yield ac
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


_ORDER_BODY = {
    "currency": "USD",
    "items": [
        {"product_id": "p1", "product_name": "Widget", "quantity": 2, "unit_amount_minor": 500},
        {"product_id": "p2", "product_name": "Gadget", "quantity": 1, "unit_amount_minor": 250},
    ],
}


async def test_create_order_computes_total(client: AsyncClient) -> None:
    resp = await client.post("/orders", json=_ORDER_BODY, headers=_auth(user_id="u1"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "created"
    assert body["user_id"] == "u1"
    assert body["total_amount_minor"] == 1250
    assert len(body["items"]) == 2


async def test_get_own_order(client: AsyncClient) -> None:
    created = await client.post("/orders", json=_ORDER_BODY, headers=_auth(user_id="u1"))
    order_id = created.json()["id"]
    resp = await client.get(f"/orders/{order_id}", headers=_auth(user_id="u1"))
    assert resp.status_code == 200
    assert resp.json()["id"] == order_id


async def test_get_cross_user_forbidden(client: AsyncClient) -> None:
    created = await client.post("/orders", json=_ORDER_BODY, headers=_auth(user_id="u1"))
    order_id = created.json()["id"]
    resp = await client.get(f"/orders/{order_id}", headers=_auth(user_id="u2"))
    assert resp.status_code == 403


async def test_invalid_transition_conflict(client: AsyncClient) -> None:
    created = await client.post("/orders", json=_ORDER_BODY, headers=_auth(user_id="u1"))
    order_id = created.json()["id"]
    # created -> shipped is not allowed.
    resp = await client.post(f"/orders/{order_id}/ship", headers=_auth(user_id="a1", role="admin"))
    assert resp.status_code == 409


async def test_pay_then_ship_flow(client: AsyncClient) -> None:
    created = await client.post("/orders", json=_ORDER_BODY, headers=_auth(user_id="u1"))
    order_id = created.json()["id"]
    admin = _auth(user_id="a1", role="admin")
    paid = await client.post(f"/orders/{order_id}/pay", headers=admin)
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"
    shipped = await client.post(f"/orders/{order_id}/ship", headers=admin)
    assert shipped.status_code == 200
    assert shipped.json()["status"] == "shipped"


async def test_refund_admin_only(client: AsyncClient) -> None:
    created = await client.post("/orders", json=_ORDER_BODY, headers=_auth(user_id="u1"))
    order_id = created.json()["id"]
    admin = _auth(user_id="a1", role="admin")
    await client.post(f"/orders/{order_id}/pay", headers=admin)
    # Customer cannot refund.
    denied = await client.post(f"/orders/{order_id}/refund", headers=_auth(user_id="u1"))
    assert denied.status_code == 403
    # Admin can refund a paid order.
    refunded = await client.post(f"/orders/{order_id}/refund", headers=admin)
    assert refunded.status_code == 200
    assert refunded.json()["status"] == "refunded"


async def test_list_own_orders(client: AsyncClient) -> None:
    await client.post("/orders", json=_ORDER_BODY, headers=_auth(user_id="u1"))
    await client.post("/orders", json=_ORDER_BODY, headers=_auth(user_id="u2"))
    resp = await client.get("/orders", headers=_auth(user_id="u1"))
    assert resp.status_code == 200
    orders = resp.json()
    assert len(orders) == 1
    assert all(o["user_id"] == "u1" for o in orders)


async def test_build_order_summary_sync(client: AsyncClient) -> None:
    from orders_api.rebuild import build_order_summary

    created = await client.post("/orders", json=_ORDER_BODY, headers=_auth(user_id="u1"))
    order_id = created.json()["id"]

    sync_db = SyncDatabase(settings().postgres_dsn)
    with sync_db.session() as session:
        projection = build_order_summary(session, order_id)
    assert projection is not None
    assert projection.order_id == order_id
    assert projection.user_id == "u1"
    assert projection.total_amount_minor == 1250
    assert projection.item_count == 3  # 2 + 1
    sync_db.engine.dispose()
