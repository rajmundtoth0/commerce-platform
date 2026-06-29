from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from cplatform.errors import NotFoundError
from cplatform.logging import get_logger
from status_api.derivation import derive_overall_status
from status_api.metrics import update_status_metrics
from status_api.models import StatusComponent, StatusIncident, StatusMaintenance, utcnow
from status_api.schemas import (
    IncidentCreate,
    IncidentUpdate,
    MaintenanceCreate,
    MaintenanceUpdate,
    StatusPayload,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("status")

_ACTIVE_MAINTENANCE = ("scheduled", "in_progress")


def _as_utc(value: datetime) -> datetime:
    """Treat tz-naive datetimes (as SQLite returns) as UTC for safe comparison."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class StatusService:
    def __init__(self, session: AsyncSession, *, recent_limit: int = 10) -> None:
        self._session = session
        self._recent_limit = recent_limit

    # --- Components ------------------------------------------------------
    async def list_components(self) -> list[StatusComponent]:
        rows = await self._session.scalars(select(StatusComponent).order_by(StatusComponent.name))
        return list(rows)

    # --- Incidents -------------------------------------------------------
    async def create_incident(self, data: IncidentCreate) -> StatusIncident:
        incident = StatusIncident(
            title=data.title,
            status=data.status,
            severity=data.severity,
            affected_components=data.affected_components,
            area=data.area,
            cause=data.cause,
            summary=data.summary,
            resolution=data.resolution,
            follow_up=data.follow_up,
            started_at=data.started_at or utcnow(),
        )
        if incident.status == "resolved":
            incident.resolved_at = utcnow()
        self._session.add(incident)
        await self._session.flush()
        await self._session.refresh(incident)
        logger.info(
            "status.incident.created",
            incident_id=incident.id,
            status=incident.status,
            severity=incident.severity,
            affected_components=incident.affected_components,
        )
        return incident

    async def get_incident(self, incident_id: str) -> StatusIncident:
        incident = await self._session.get(StatusIncident, incident_id)
        if incident is None or incident.deleted_at is not None:
            raise NotFoundError(f"Incident '{incident_id}' not found", details={"id": incident_id})
        return incident

    async def list_incidents(self) -> list[StatusIncident]:
        rows = await self._session.scalars(
            select(StatusIncident)
            .where(StatusIncident.deleted_at.is_(None))
            .order_by(StatusIncident.started_at.desc())
        )
        return list(rows)

    async def list_active_incidents(self) -> list[StatusIncident]:
        rows = await self._session.scalars(
            select(StatusIncident)
            .where(StatusIncident.deleted_at.is_(None), StatusIncident.status != "resolved")
            .order_by(StatusIncident.started_at.desc())
        )
        return list(rows)

    async def list_recent_incidents(self) -> list[StatusIncident]:
        rows = await self._session.scalars(
            select(StatusIncident)
            .where(StatusIncident.deleted_at.is_(None), StatusIncident.status == "resolved")
            .order_by(StatusIncident.resolved_at.desc())
            .limit(self._recent_limit)
        )
        return list(rows)

    async def update_incident(self, incident_id: str, data: IncidentUpdate) -> StatusIncident:
        incident = await self.get_incident(incident_id)
        patch = data.model_dump(exclude_unset=True)
        became_resolved = patch.get("status") == "resolved" and incident.status != "resolved"
        for field, value in patch.items():
            setattr(incident, field, value)
        if incident.status == "resolved" and incident.resolved_at is None:
            incident.resolved_at = utcnow()
        if incident.status != "resolved":
            incident.resolved_at = None
        await self._session.flush()
        await self._session.refresh(incident)
        logger.info(
            "status.incident.updated",
            incident_id=incident.id,
            status=incident.status,
            severity=incident.severity,
            affected_components=incident.affected_components,
        )
        if became_resolved:
            logger.info(
                "status.incident.resolved", incident_id=incident.id, severity=incident.severity
            )
        return incident

    async def delete_incident(self, incident_id: str) -> None:
        incident = await self.get_incident(incident_id)
        incident.deleted_at = utcnow()
        await self._session.flush()
        logger.info("status.incident.deleted", incident_id=incident.id)

    # --- Maintenance -----------------------------------------------------
    async def create_maintenance(self, data: MaintenanceCreate) -> StatusMaintenance:
        window = StatusMaintenance(
            title=data.title,
            status=data.status,
            affected_components=data.affected_components,
            summary=data.summary,
            scheduled_start_at=data.scheduled_start_at,
            scheduled_end_at=data.scheduled_end_at,
        )
        if window.status == "in_progress":
            window.started_at = utcnow()
        elif window.status == "completed":
            window.completed_at = utcnow()
        self._session.add(window)
        await self._session.flush()
        await self._session.refresh(window)
        logger.info(
            "status.maintenance.created",
            maintenance_id=window.id,
            status=window.status,
            affected_components=window.affected_components,
        )
        return window

    async def get_maintenance(self, maintenance_id: str) -> StatusMaintenance:
        window = await self._session.get(StatusMaintenance, maintenance_id)
        if window is None or window.deleted_at is not None:
            raise NotFoundError(
                f"Maintenance '{maintenance_id}' not found", details={"id": maintenance_id}
            )
        return window

    async def list_maintenance(self) -> list[StatusMaintenance]:
        rows = await self._session.scalars(
            select(StatusMaintenance)
            .where(StatusMaintenance.deleted_at.is_(None))
            .order_by(StatusMaintenance.scheduled_start_at.desc())
        )
        return list(rows)

    async def list_planned_maintenance(self) -> list[StatusMaintenance]:
        rows = await self._session.scalars(
            select(StatusMaintenance)
            .where(
                StatusMaintenance.deleted_at.is_(None),
                StatusMaintenance.status.in_(_ACTIVE_MAINTENANCE),
            )
            .order_by(StatusMaintenance.scheduled_start_at.asc())
        )
        return list(rows)

    async def update_maintenance(
        self, maintenance_id: str, data: MaintenanceUpdate
    ) -> StatusMaintenance:
        window = await self.get_maintenance(maintenance_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(window, field, value)
        if window.status == "in_progress" and window.started_at is None:
            window.started_at = utcnow()
        if window.status == "completed" and window.completed_at is None:
            window.completed_at = utcnow()
        await self._session.flush()
        await self._session.refresh(window)
        logger.info("status.maintenance.updated", maintenance_id=window.id, status=window.status)
        return window

    async def delete_maintenance(self, maintenance_id: str) -> None:
        window = await self.get_maintenance(maintenance_id)
        window.deleted_at = utcnow()
        await self._session.flush()
        logger.info("status.maintenance.deleted", maintenance_id=window.id)

    # --- Status payload --------------------------------------------------
    async def build_status_payload(self) -> StatusPayload:
        components = await self.list_components()
        active = await self.list_active_incidents()
        recent = await self.list_recent_incidents()
        planned = await self.list_planned_maintenance()

        now = utcnow()
        maintenance_active = any(
            w.status == "in_progress"
            or (
                w.status == "scheduled"
                and _as_utc(w.scheduled_start_at) <= now <= _as_utc(w.scheduled_end_at)
            )
            for w in planned
        )
        overall = derive_overall_status(
            component_statuses=[c.status for c in components],
            incident_severities=[i.severity for i in active],
            maintenance_active=maintenance_active,
        )

        all_maintenance = await self.list_maintenance()
        update_status_metrics(
            component_statuses=[c.status for c in components],
            active_severities=[i.severity for i in active],
            maintenance_statuses=[w.status for w in all_maintenance],
        )

        return StatusPayload.model_validate(
            {
                "overall_status": overall,
                "updated_at": now,
                "components": components,
                "active_incidents": active,
                "recent_incidents": recent,
                "planned_maintenance": planned,
            }
        )
