"""Overall status derivation — a single pure, testable function."""

from __future__ import annotations

from collections.abc import Iterable

from status_api.schemas import OverallStatus

_COMPONENT_DEGRADED = {"degraded", "down"}


def derive_overall_status(
    *,
    component_statuses: Iterable[str],
    incident_severities: Iterable[str],
    maintenance_active: bool,
) -> OverallStatus:
    """Derive the overall status (highest concern wins).

    critical incident      -> major_outage
    major incident         -> partial_outage
    minor incident OR any component degraded/down -> degraded
    maintenance active (and nothing worse)        -> maintenance
    otherwise              -> operational
    no/only-unknown components (and nothing wrong) -> unknown
    """
    severities = set(incident_severities)
    components = list(component_statuses)

    if "critical" in severities:
        return "major_outage"
    if "major" in severities:
        return "partial_outage"
    if "minor" in severities or any(s in _COMPONENT_DEGRADED for s in components):
        return "degraded"
    if maintenance_active:
        return "maintenance"
    if not components or all(s == "unknown" for s in components):
        return "unknown"
    return "operational"
