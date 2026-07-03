"""status-api: derivation logic, public reads, token-gated writes, lifecycles."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from status_api.checks import CheckOutcome, map_outcome_to_status
from status_api.derivation import derive_overall_status

TOKEN = "test-ops-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest_asyncio.fixture
async def status_client() -> AsyncClient:
    from status_api.deps import database
    from status_api.main import app
    from status_api.models import Base

    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://status") as client:
            yield client
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# --- pure unit tests ------------------------------------------------------
def test_component_status_mapping() -> None:
    assert map_outcome_to_status(CheckOutcome("ok")) == "operational"
    assert map_outcome_to_status(CheckOutcome("bad_status", http_status=503)) == "degraded"
    assert map_outcome_to_status(CheckOutcome("timeout")) == "down"
    assert map_outcome_to_status(CheckOutcome("conn_error")) == "down"
    assert map_outcome_to_status(CheckOutcome("unknown")) == "unknown"


def test_overall_status_derivation() -> None:
    d = derive_overall_status
    assert (
        d(
            component_statuses=["operational"],
            incident_severities=["critical"],
            maintenance_active=False,
        )
        == "major_outage"
    )
    assert (
        d(
            component_statuses=["operational"],
            incident_severities=["major"],
            maintenance_active=False,
        )
        == "partial_outage"
    )
    assert (
        d(
            component_statuses=["operational"],
            incident_severities=["minor"],
            maintenance_active=False,
        )
        == "degraded"
    )
    assert (
        d(component_statuses=["degraded"], incident_severities=[], maintenance_active=False)
        == "degraded"
    )
    assert (
        d(component_statuses=["operational"], incident_severities=[], maintenance_active=True)
        == "maintenance"
    )
    assert (
        d(component_statuses=["operational"], incident_severities=[], maintenance_active=False)
        == "operational"
    )
    assert (
        d(component_statuses=["unknown"], incident_severities=[], maintenance_active=False)
        == "unknown"
    )
    # outage beats maintenance
    assert (
        d(
            component_statuses=["operational"],
            incident_severities=["critical"],
            maintenance_active=True,
        )
        == "major_outage"
    )


# --- API tests ------------------------------------------------------------
async def test_get_status_payload(status_client: AsyncClient) -> None:
    resp = await status_client.get("/status")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "overall_status",
        "updated_at",
        "components",
        "active_incidents",
        "recent_incidents",
        "planned_maintenance",
    ):
        assert key in body
    # components were seeded on startup from the default checks
    assert any(c["id"] == "webshop-api" for c in body["components"])


async def test_status_page_served(status_client: AsyncClient) -> None:
    resp = await status_client.get("/")
    assert resp.status_code == 200
    assert "Internal Status" in resp.text


async def test_create_incident_requires_token(status_client: AsyncClient) -> None:
    resp = await status_client.post("/status/incidents", json={"title": "x"})
    assert resp.status_code == 401


async def test_create_incident_wrong_token(status_client: AsyncClient) -> None:
    resp = await status_client.post(
        "/status/incidents", json={"title": "x"}, headers={"Authorization": "Bearer nope"}
    )
    assert resp.status_code == 403


async def test_create_incident_with_token(status_client: AsyncClient) -> None:
    resp = await status_client.post(
        "/status/incidents",
        headers=AUTH,
        json={
            "title": "Pricing API degraded",
            "status": "investigating",
            "severity": "major",
            "affected_components": ["pricing-api", "webshop-api"],
            "area": "backend",
            "cause": "dependency_failure",
            "summary": "Elevated latency.",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["severity"] == "major"
    assert body["resolved_at"] is None


async def test_incident_lifecycle(status_client: AsyncClient) -> None:
    created = await status_client.post(
        "/status/incidents",
        headers=AUTH,
        json={"title": "Cache sync lag", "status": "investigating", "severity": "minor"},
    )
    incident_id = created.json()["id"]

    # appears in active, not recent
    status = (await status_client.get("/status")).json()
    assert any(i["id"] == incident_id for i in status["active_incidents"])
    assert all(i["id"] != incident_id for i in status["recent_incidents"])

    # resolve it
    patched = await status_client.patch(
        f"/status/incidents/{incident_id}",
        headers=AUTH,
        json={"status": "resolved", "resolution": "Projection rebuilt."},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "resolved"
    assert patched.json()["resolved_at"] is not None

    # now in recent, not active
    status = (await status_client.get("/status")).json()
    assert all(i["id"] != incident_id for i in status["active_incidents"])
    assert any(i["id"] == incident_id for i in status["recent_incidents"])


async def test_active_critical_incident_changes_overall(status_client: AsyncClient) -> None:
    await status_client.post(
        "/status/incidents",
        headers=AUTH,
        json={"title": "DB down", "status": "investigating", "severity": "critical"},
    )
    body = (await status_client.get("/status")).json()
    assert body["overall_status"] == "major_outage"


async def test_delete_incident_soft(status_client: AsyncClient) -> None:
    created = await status_client.post(
        "/status/incidents", headers=AUTH, json={"title": "Temp", "severity": "minor"}
    )
    incident_id = created.json()["id"]
    assert (
        await status_client.delete(f"/status/incidents/{incident_id}", headers=AUTH)
    ).status_code == 204
    assert (await status_client.get(f"/status/incidents/{incident_id}")).status_code == 404


async def test_maintenance_crud(status_client: AsyncClient) -> None:
    start = datetime.now(UTC) + timedelta(hours=1)
    end = start + timedelta(minutes=15)
    created = await status_client.post(
        "/status/maintenance",
        headers=AUTH,
        json={
            "title": "Valkey restart",
            "status": "scheduled",
            "affected_components": ["valkey", "webshop-api"],
            "summary": "Restart Valkey.",
            "scheduled_start_at": start.isoformat(),
            "scheduled_end_at": end.isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    mid = created.json()["id"]

    # appears in planned maintenance on the status page
    body = (await status_client.get("/status")).json()
    assert any(m["id"] == mid for m in body["planned_maintenance"])

    # update + soft delete
    patched = await status_client.patch(
        f"/status/maintenance/{mid}", headers=AUTH, json={"status": "in_progress"}
    )
    assert patched.json()["status"] == "in_progress"
    assert patched.json()["started_at"] is not None
    assert (
        await status_client.delete(f"/status/maintenance/{mid}", headers=AUTH)
    ).status_code == 204
    assert (await status_client.get(f"/status/maintenance/{mid}")).status_code == 404


async def test_maintenance_requires_token(status_client: AsyncClient) -> None:
    resp = await status_client.post("/status/maintenance", json={"title": "x"})
    assert resp.status_code == 401
