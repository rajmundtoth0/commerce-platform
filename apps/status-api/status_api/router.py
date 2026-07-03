from __future__ import annotations

from fastapi import APIRouter, Response, status
from fastapi.responses import HTMLResponse

from status_api.deps import OpsToken, ServiceDep
from status_api.page import STATUS_PAGE_HTML
from status_api.schemas import (
    ComponentRead,
    IncidentCreate,
    IncidentRead,
    IncidentUpdate,
    MaintenanceCreate,
    MaintenanceRead,
    MaintenanceUpdate,
    StatusPayload,
)

page_router = APIRouter(include_in_schema=False)
status_router = APIRouter(prefix="/status", tags=["status"])


@page_router.get("/", response_class=HTMLResponse)
async def status_page() -> HTMLResponse:
    return HTMLResponse(STATUS_PAGE_HTML)


# --- Read (public) --------------------------------------------------------
@status_router.get("", response_model=StatusPayload)
async def get_status(service: ServiceDep) -> StatusPayload:
    return await service.build_status_payload()


@status_router.get("/components", response_model=list[ComponentRead])
async def list_components(service: ServiceDep) -> list[ComponentRead]:
    return [ComponentRead.model_validate(c) for c in await service.list_components()]


@status_router.get("/incidents", response_model=list[IncidentRead])
async def list_incidents(service: ServiceDep) -> list[IncidentRead]:
    return [IncidentRead.model_validate(i) for i in await service.list_incidents()]


@status_router.get("/incidents/{incident_id}", response_model=IncidentRead)
async def get_incident(incident_id: str, service: ServiceDep) -> IncidentRead:
    return IncidentRead.model_validate(await service.get_incident(incident_id))


@status_router.get("/maintenance", response_model=list[MaintenanceRead])
async def list_maintenance(service: ServiceDep) -> list[MaintenanceRead]:
    return [MaintenanceRead.model_validate(m) for m in await service.list_maintenance()]


@status_router.get("/maintenance/{maintenance_id}", response_model=MaintenanceRead)
async def get_maintenance(maintenance_id: str, service: ServiceDep) -> MaintenanceRead:
    return MaintenanceRead.model_validate(await service.get_maintenance(maintenance_id))


# --- Write (require ops token) -------------------------------------------
@status_router.post("/incidents", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def create_incident(data: IncidentCreate, service: ServiceDep, _: OpsToken) -> IncidentRead:
    return IncidentRead.model_validate(await service.create_incident(data))


@status_router.patch("/incidents/{incident_id}", response_model=IncidentRead)
async def update_incident(
    incident_id: str, data: IncidentUpdate, service: ServiceDep, _: OpsToken
) -> IncidentRead:
    return IncidentRead.model_validate(await service.update_incident(incident_id, data))


@status_router.delete("/incidents/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident(incident_id: str, service: ServiceDep, _: OpsToken) -> Response:
    await service.delete_incident(incident_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@status_router.post(
    "/maintenance", response_model=MaintenanceRead, status_code=status.HTTP_201_CREATED
)
async def create_maintenance(
    data: MaintenanceCreate, service: ServiceDep, _: OpsToken
) -> MaintenanceRead:
    return MaintenanceRead.model_validate(await service.create_maintenance(data))


@status_router.patch("/maintenance/{maintenance_id}", response_model=MaintenanceRead)
async def update_maintenance(
    maintenance_id: str, data: MaintenanceUpdate, service: ServiceDep, _: OpsToken
) -> MaintenanceRead:
    return MaintenanceRead.model_validate(await service.update_maintenance(maintenance_id, data))


@status_router.delete("/maintenance/{maintenance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_maintenance(maintenance_id: str, service: ServiceDep, _: OpsToken) -> Response:
    await service.delete_maintenance(maintenance_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
