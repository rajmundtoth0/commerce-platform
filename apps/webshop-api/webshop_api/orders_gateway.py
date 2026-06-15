"""Gateway to orders-api.

webshop-api does NOT write order tables — it calls orders-api over HTTP. Because
all services share the JWT secret, the BFF mints a short-lived customer access
token for the (guest) shopper and forwards it; orders-api enforces the token like
any other caller. This keeps the auth boundary real: orders-api trusts the token,
not the caller.

Simplification: guest checkout derives a stable user id from the email rather
than creating a full account in auth-api. A production flow would authenticate
the customer with auth-api first; the order-creation boundary would be identical.
"""

from __future__ import annotations

import hashlib

from cplatform.auth import issue_token
from cplatform.http import ServiceClient
from webshop_api.schemas import OrderOut
from webshop_api.settings import WebshopSettings


def guest_user_id(email: str) -> str:
    return "guest:" + hashlib.sha256(email.lower().encode()).hexdigest()[:24]


class OrdersGateway:
    def __init__(self, settings: WebshopSettings) -> None:
        self._settings = settings
        self._client = ServiceClient(settings.orders_api_url, name="orders-api")

    def _token(self, email: str) -> str:
        s = self._settings
        return issue_token(
            user_id=guest_user_id(email),
            email=email,
            role="customer",
            token_type="access",
            secret=s.jwt_secret,
            algorithm=s.jwt_algorithm,
            ttl_seconds=300,
        )

    async def create_order(
        self, *, email: str, currency: str, items: list[dict[str, object]]
    ) -> OrderOut:
        body = await self._client.request(
            "POST",
            "/orders",
            bearer=self._token(email),
            json={"currency": currency, "items": items},
        )
        return OrderOut.model_validate(body)

    async def get_order(self, *, email: str, order_id: str) -> OrderOut:
        body = await self._client.request("GET", f"/orders/{order_id}", bearer=self._token(email))
        return OrderOut.model_validate(body)

    async def aclose(self) -> None:
        await self._client.aclose()
