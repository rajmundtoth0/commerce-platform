from __future__ import annotations

from cplatform.logging import get_logger
from cplatform.service import create_service_app
from orders_api.deps import database
from orders_api.router import orders_router
from orders_api.settings import settings

_settings = settings()
logger = get_logger(_settings.service_name)


app = create_service_app(
    settings=_settings,
    title="orders-api",
    routers=[orders_router],
    readiness_checks=[("postgres", database.ping)],
    engine=database.engine,
    on_shutdown=database.dispose,
)
