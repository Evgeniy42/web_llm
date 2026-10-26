import logging
import subprocess
from contextlib import asynccontextmanager

from dishka import make_container
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from sqlalchemy import text

from app.configuration.container import AppProvider
from app.configuration.database import DatabaseManager
from app.configuration.settings import Settings
from app.presentation_layer.handlers.http_exception_handlers import setup_exception_handlers

logger = logging.getLogger(__name__)


def run_migrations(settings: Settings) -> None:
    """Запускает Flyway-миграции через flyway CLI."""
    result = subprocess.run(
        [
            "flyway",
            "migrate",
            f"-url=jdbc:postgresql://{settings.db_host}:{settings.db_port}/{settings.db_name}",
            f"-user={settings.db_user}",
            f"-password={settings.db_password}",
            "-locations=filesystem:/app/app/migrations/sql",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Flyway migration failed: {result.stderr or result.stdout}")


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    db_manager = DatabaseManager(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            run_migrations(settings)
            with db_manager.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            yield
        finally:
            db_manager.dispose()

    app = FastAPI(title="Web LLM", lifespan=lifespan)
    app.state.settings = settings
    app.state.db_manager = db_manager

    setup_exception_handlers(app)

    container = make_container(AppProvider())
    setup_dishka(container, app)

    from app.presentation_layer.controllers.api.v1.chat_router import router as chat_router
    from app.presentation_layer.controllers.api.v1.user_router import router as user_router
    from app.presentation_layer.controllers.health import router as health_router

    app.include_router(health_router)
    app.include_router(user_router)
    app.include_router(chat_router)

    return app
