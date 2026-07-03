from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OverallStatus = Literal[
    "operational", "degraded", "partial_outage", "major_outage", "maintenance", "unknown"
]
ComponentStatus = Literal["operational", "degraded", "down", "maintenance", "unknown"]
IncidentStatus = Literal["investigating", "identified", "monitoring", "resolved"]
IncidentSeverity = Literal["minor", "major", "critical"]
IncidentArea = Literal["platform", "backend", "frontend", "external_provider", "unknown"]
IncidentCause = Literal[
    "deployment",
    "migration",
    "infrastructure",
    "third_party",
    "config",
    "data_import",
    "code_bug",
    "cache_sync",
    "dependency_failure",
    "unknown",
]
MaintenanceStatus = Literal["scheduled", "in_progress", "completed", "cancelled"]


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Components -----------------------------------------------------------
class ComponentRead(_ORM):
    id: str
    name: str
    description: str = ""
    status: ComponentStatus
    last_checked_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error: str | None = None


# --- Incidents ------------------------------------------------------------
class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    status: IncidentStatus = "investigating"
    severity: IncidentSeverity = "minor"
    affected_components: list[str] = Field(default_factory=list)
    area: IncidentArea = "unknown"
    cause: IncidentCause = "unknown"
    summary: str = ""
    resolution: str | None = None
    follow_up: str | None = None
    started_at: datetime | None = None


class IncidentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: IncidentStatus | None = None
    severity: IncidentSeverity | None = None
    affected_components: list[str] | None = None
    area: IncidentArea | None = None
    cause: IncidentCause | None = None
    summary: str | None = None
    resolution: str | None = None
    follow_up: str | None = None


class IncidentRead(_ORM):
    id: str
    title: str
    status: IncidentStatus
    severity: IncidentSeverity
    affected_components: list[str]
    area: IncidentArea
    cause: IncidentCause
    summary: str
    resolution: str | None = None
    follow_up: str | None = None
    started_at: datetime
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# --- Maintenance ----------------------------------------------------------
class MaintenanceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    status: MaintenanceStatus = "scheduled"
    affected_components: list[str] = Field(default_factory=list)
    summary: str = ""
    scheduled_start_at: datetime
    scheduled_end_at: datetime


class MaintenanceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: MaintenanceStatus | None = None
    affected_components: list[str] | None = None
    summary: str | None = None
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None


class MaintenanceRead(_ORM):
    id: str
    title: str
    status: MaintenanceStatus
    affected_components: list[str]
    summary: str
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# --- Status page payload --------------------------------------------------
class StatusPayload(_ORM):
    overall_status: OverallStatus
    updated_at: datetime
    components: list[ComponentRead]
    active_incidents: list[IncidentRead]
    recent_incidents: list[IncidentRead]
    planned_maintenance: list[MaintenanceRead]
