"""webshop-api BFF: catalog from projections, Valkey cart, checkout via orders gateway."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from webshop_api.schemas import OrderItemOut, OrderOut

from cplatform.contracts import (
    PRODUCT_PRICE_SPEC,
    PRODUCT_SPEC,
    ProductPriceProjection,
    ProductProjection,
)
from cplatform.projections import SyncProjectionWriter
from cplatform.valkey import get_sync_valkey

pytestmark = pytest.mark.asyncio

VALKEY_URL = "redis://localhost:6380/0"


def _seed_product(pid: str, *, featured: bool, amount: int | None) -> None:
    sync = get_sync_valkey(VALKEY_URL)
    SyncProjectionWriter(PRODUCT_SPEC, sync, service="test").write(
        pid,
        ProductProjection(
            id=pid,
            sku=f"SKU-{pid}",
            name=f"Product {pid}",
            description="d",
            active=True,
            featured=featured,
        ),
    )
    if amount is not None:
        SyncProjectionWriter(PRODUCT_PRICE_SPEC, sync, service="test").write(
            pid, ProductPriceProjection(product_id=pid, currency="USD", amount_minor=amount)
        )


class _FakeOrdersGateway:
    def __init__(self) -> None:
        self.created: list[dict] = []

    async def create_order(self, *, email: str, currency: str, items: list[dict]) -> OrderOut:
        self.created.append({"email": email, "currency": currency, "items": items})
        total = sum(i["unit_amount_minor"] * i["quantity"] for i in items)
        return OrderOut(
            id="order-1",
            status="created",
            currency=currency,
            total_amount_minor=total,
            items=[OrderItemOut(**i) for i in items],
        )

    async def get_order(self, *, email: str, order_id: str) -> OrderOut:
        return OrderOut(id=order_id, status="paid", currency="USD", total_amount_minor=0, items=[])


@pytest_asyncio.fixture
async def webshop() -> AsyncClient:
    from webshop_api.deps import get_orders_gateway
    from webshop_api.main import app

    fake = _FakeOrdersGateway()
    app.dependency_overrides[get_orders_gateway] = lambda: fake
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://webshop") as client:
            client._fake_orders = fake  # type: ignore[attr-defined]
            yield client
    app.dependency_overrides.clear()


async def test_featured_and_listing(webshop: AsyncClient) -> None:
    _seed_product("a", featured=True, amount=1500)
    _seed_product("b", featured=False, amount=2000)

    featured = await webshop.get("/catalog/featured")
    assert featured.status_code == 200
    assert [p["id"] for p in featured.json()] == ["a"]

    listing = await webshop.get("/catalog/products")
    assert listing.json()["total"] == 2


async def test_product_detail_joins_price(webshop: AsyncClient) -> None:
    _seed_product("p", featured=False, amount=999)
    resp = await webshop.get("/catalog/products/p")
    assert resp.status_code == 200
    body = resp.json()
    assert body["amount_minor"] == 999 and body["currency"] == "USD"


async def test_missing_product_404(webshop: AsyncClient) -> None:
    assert (await webshop.get("/catalog/products/nope")).status_code == 404


async def test_cart_flow_and_totals(webshop: AsyncClient) -> None:
    _seed_product("x", featured=False, amount=1000)
    cart_id = "cart-123"
    add = await webshop.post(f"/cart/{cart_id}/items", json={"product_id": "x", "quantity": 3})
    assert add.status_code == 201
    body = add.json()
    assert body["total_amount_minor"] == 3000
    assert body["has_unpriced_items"] is False

    view = await webshop.get(f"/cart/{cart_id}")
    assert view.json()["items"][0]["quantity"] == 3


async def test_add_unknown_product_404(webshop: AsyncClient) -> None:
    resp = await webshop.post("/cart/c/items", json={"product_id": "ghost", "quantity": 1})
    assert resp.status_code == 404


async def test_checkout_calls_orders_and_clears_cart(webshop: AsyncClient) -> None:
    _seed_product("y", featured=False, amount=2500)
    cart_id = "cart-checkout"
    await webshop.post(f"/cart/{cart_id}/items", json={"product_id": "y", "quantity": 2})

    resp = await webshop.post(f"/checkout/{cart_id}", json={"email": "shopper@example.com"})
    assert resp.status_code == 201, resp.text
    order = resp.json()
    assert order["total_amount_minor"] == 5000
    assert order["id"] == "order-1"

    # Gateway was called and the cart was emptied.
    fake = webshop._fake_orders  # type: ignore[attr-defined]
    assert fake.created[0]["email"] == "shopper@example.com"
    assert (await webshop.get(f"/cart/{cart_id}")).json()["items"] == []


async def test_checkout_empty_cart_409(webshop: AsyncClient) -> None:
    resp = await webshop.post("/checkout/empty-cart", json={"email": "a@b.com"})
    assert resp.status_code == 409
