"""Idempotent admin seeding.

Used in two places:
  * the migration Job (after Alembic) — the authoritative place in Kubernetes,
    since the schema is created by that same Job;
  * auth-api startup (best-effort) — convenient for local/compose runs.

Both call `seed_admin`, which is a no-op when the admin already exists.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from auth_api.schemas import RegisterRequest
from auth_api.service import AuthService
from auth_api.settings import AuthSettings


async def seed_admin(session: AsyncSession, settings: AuthSettings) -> bool:
    """Create the seed admin if absent. Returns True if it was created."""
    service = AuthService(session, settings)
    if await service._by_email(settings.seed_admin_email) is not None:
        return False
    await service.register(
        RegisterRequest(
            email=settings.seed_admin_email,
            full_name="Seed Admin",
            password=settings.seed_admin_password,
        ),
        role="admin",
    )
    return True


async def _main() -> None:
    from auth_api.deps import database
    from auth_api.settings import settings

    cfg = settings()
    async with database.sessionmaker() as session:
        created = await seed_admin(session, cfg)
        await session.commit()
    await database.dispose()
    print(f"seed admin {cfg.seed_admin_email}: {'created' if created else 'already exists'}")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
