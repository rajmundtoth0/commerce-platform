from __future__ import annotations

from backoffice_api.deps import database
from backoffice_api.router import admin_router, products_router
from backoffice_api.settings import settings
from cplatform.logging import get_logger
from cplatform.service import create_service_app

_settings = settings()
logger = get_logger(_settings.service_name)

app = create_service_app(
    settings=_settings,
    title="backoffice-api",
    routers=[products_router, admin_router],
    readiness_checks=[("postgres", database.ping)],
    engine=database.engine,
    on_shutdown=database.dispose,
)

# Mount the SQLAdmin UI AFTER the app is built (it uses the async engine).
# Guarded so a SQLAdmin integration hiccup can never break /health or the API.
try:
    from backoffice_api.admin import mount_admin

    mount_admin(app, database.engine, _settings)
except Exception as exc:  # pragma: no cover - defensive; UI is non-critical.
    logger.warning("admin.mount.failed", error=str(exc))
