"""Prometheus gauges for the status page (default registry -> exposed at /metrics)."""

from __future__ import annotations

from collections.abc import Iterable

from prometheus_client import Gauge

COMPONENTS = Gauge("status_components_total", "Components by status.", ["status"])
ACTIVE_INCIDENTS = Gauge(
    "status_active_incidents_total", "Active (unresolved) incidents by severity.", ["severity"]
)
MAINTENANCE = Gauge(
    "status_maintenance_windows_total", "Maintenance windows by status.", ["status"]
)

_COMPONENT_STATUSES = ("operational", "degraded", "down", "maintenance", "unknown")
_SEVERITIES = ("minor", "major", "critical")
_MAINTENANCE_STATUSES = ("scheduled", "in_progress", "completed", "cancelled")


def _set(gauge: Gauge, label: str, values: Iterable[str], universe: tuple[str, ...]) -> None:
    counts = dict.fromkeys(universe, 0)
    for v in values:
        if v in counts:
            counts[v] += 1
    for key, n in counts.items():
        gauge.labels(**{label: key}).set(n)


def update_status_metrics(
    *,
    component_statuses: Iterable[str],
    active_severities: Iterable[str],
    maintenance_statuses: Iterable[str],
) -> None:
    _set(COMPONENTS, "status", component_statuses, _COMPONENT_STATUSES)
    _set(ACTIVE_INCIDENTS, "severity", active_severities, _SEVERITIES)
    _set(MAINTENANCE, "status", maintenance_statuses, _MAINTENANCE_STATUSES)
