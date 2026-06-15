from __future__ import annotations

from auth_api.deps import database
from auth_api.router import auth_router, users_router
from auth_api.schemas import RegisterRequest
from auth_api.service import AuthService
from auth_api.settings import settings
from cplatform.logging import get_logger
from cplatform.service import create_service_app

_settings = settings()
logger = get_logger(_settings.service_name)


async def _seed_admin() -> None:
    """Best-effort seed of an initial admin (local/dev convenience)."""
    try:
        async with database.sessionmaker() as session:
            service = AuthService(session, _settings)
            existing = await service._by_email(_settings.seed_admin_email)
            if existing is None:
                await service.register(
                    RegisterRequest(
                        email=_settings.seed_admin_email,
                        full_name="Seed Admin",
                        password=_settings.seed_admin_password,
                    ),
                    role="admin",
                )
                await session.commit()
                logger.info("auth.seed.admin.created", email=_settings.seed_admin_email)
    except Exception as exc:  # never block startup on seeding.
        logger.warning("auth.seed.admin.failed", error=str(exc))


app = create_service_app(
    settings=_settings,
    title="auth-api",
    routers=[auth_router, users_router],
    readiness_checks=[("postgres", database.ping)],
    engine=database.engine,
    on_startup=_seed_admin,
    on_shutdown=database.dispose,
)
