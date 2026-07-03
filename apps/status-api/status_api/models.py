from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, MetaData, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from cplatform.db import NAMING_CONVENTION, TimestampMixin


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class StatusComponent(Base, TimestampMixin):
    __tablename__ = "status_components"

    # id is the stable component key (e.g. "webshop-api"), set from the check spec.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class StatusIncident(Base, TimestampMixin):
    __tablename__ = "status_incidents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="investigating")
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="minor")
    affected_components: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    area: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    cause: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resolution: Mapped[str | None] = mapped_column(Text)
    follow_up: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StatusMaintenance(Base, TimestampMixin):
    __tablename__ = "status_maintenance_windows"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    affected_components: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    scheduled_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
