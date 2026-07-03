"""Health collector: runs the configured checks and upserts component rows.

Checks run concurrently with short timeouts so one slow dependency can't stall
the refresh. The collector is decoupled from the read path — `GET /status` reads
the stored component rows; this just keeps them current (seeded on startup, then
refreshed on an interval; also triggerable on demand).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx

from cplatform.db import Database
from cplatform.logging import get_logger
from status_api.checks import CheckOutcome, CheckSpec, map_outcome_to_status, run_check
from status_api.models import StatusComponent, utcnow

logger = get_logger("status.health")

Checker = Callable[[CheckSpec], Awaitable[CheckOutcome]]


class HealthCollector:
    def __init__(self, database: Database, checks: list[CheckSpec], *, timeout: float) -> None:
        self._database = database
        self._checks = checks
        self._timeout = timeout

    async def seed(self) -> None:
        """Create component rows for configured checks that don't exist yet."""
        async with self._database.sessionmaker() as session:
            for spec in self._checks:
                if await session.get(StatusComponent, spec.id) is None:
                    session.add(
                        StatusComponent(
                            id=spec.id,
                            name=spec.name,
                            description=spec.description,
                            status="unknown",
                        )
                    )
            await session.commit()

    async def refresh(self, checker: Checker | None = None) -> None:
        if checker is None:
            async with httpx.AsyncClient() as client:

                async def _default(spec: CheckSpec) -> CheckOutcome:
                    return await run_check(spec, client=client, timeout_s=self._timeout)

                results = await self._run_all(_default)
        else:
            results = await self._run_all(checker)
        await self._apply(results)
        logger.info("status.health.refreshed", count=len(results))

    async def _run_all(self, checker: Checker) -> list[tuple[CheckSpec, CheckOutcome]]:
        outcomes = await asyncio.gather(*(checker(spec) for spec in self._checks))
        return list(zip(self._checks, outcomes, strict=True))

    async def _apply(self, results: list[tuple[CheckSpec, CheckOutcome]]) -> None:
        now = utcnow()
        async with self._database.sessionmaker() as session:
            for spec, outcome in results:
                component = await session.get(StatusComponent, spec.id)
                if component is None:
                    component = StatusComponent(
                        id=spec.id, name=spec.name, description=spec.description
                    )
                    session.add(component)
                component.status = map_outcome_to_status(outcome)
                component.last_checked_at = now
                component.last_error = outcome.error
                if component.status == "operational":
                    component.last_success_at = now
                else:
                    component.last_failure_at = now
            await session.commit()
