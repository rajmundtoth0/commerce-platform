from __future__ import annotations

from auth_api.deps import database
from auth_api.router import auth_router, users_router
from auth_api.seed import seed_admin
from auth_api.settings import settings
from cplatform.logging import get_logger
from cplatform.service import create_service_app

_settings = settings()
logger = get_logger(_settings.service_name)


async def _seed_admin() -> None:
    """Best-effort seed at startup (local/compose). In Kubernetes the migration
    Job is the authoritative seeder, since it owns schema creation."""
    try:
        async with database.sessionmaker() as session:
            created = await seed_admin(session, _settings)
            await session.commit()
        if created:
            logger.info("auth.seed.admin.created", email=_settings.seed_admin_email)
    except Exception as exc:  # never block startup on seeding.
        logger.warning("auth.seed.admin.skipped", error=str(exc))


app = create_service_app(
    settings=_settings,
    title="auth-api",
    routers=[auth_router, users_router],
    readiness_checks=[("postgres", database.ping)],
    engine=database.engine,
    on_startup=_seed_admin,
    on_shutdown=database.dispose,
)
