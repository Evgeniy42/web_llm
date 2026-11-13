import logging
import subprocess
import sys
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from dishka import make_async_container
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.application_layer.contracts.keycloak_protocol import KeycloakClientProtocol
from app.configuration.container import AppProvider
from app.configuration.database import DatabaseManager
from app.configuration.settings import Settings
from app.data_access_layer.keycloak_client import KeycloakClient
from app.presentation_layer.handlers.http_exception_handlers import setup_exception_handlers

logger = logging.getLogger(__name__)


def run_migrations(settings: Settings) -> None:
    """Запускает Flyway-миграции через flyway CLI."""
    flyway_cmd = "flyway.cmd" if sys.platform == "win32" else "flyway"
    flyway_path = shutil.which(flyway_cmd)

    if flyway_path is None:
        raise FileNotFoundError(f"{flyway_cmd} не найден в PATH")

    project_root = Path(__file__).resolve().parents[2]
    migrations_path = project_root / "app" / "migrations" / "sql"

    result = subprocess.run(
        [
            flyway_path,
            "migrate",
            f"-url=jdbc:postgresql://{settings.db_host}:{settings.db_port}/{settings.db_name}",
            f"-user={settings.db_user}",
            f"-password={settings.db_password}",
            f"-locations=filesystem:{migrations_path}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Flyway migration failed: {result.stderr or result.stdout}")


def create_app(
    settings: Settings | None = None,
    keycloak_client: KeycloakClientProtocol | None = None,
) -> FastAPI:
    if settings is None:
        settings = Settings()

    db_manager = DatabaseManager(settings.database_url)
    if keycloak_client is None:
        keycloak_client = KeycloakClient(
            base_url=settings.keycloak_url,
            realm=settings.keycloak_realm,
            client_id=settings.keycloak_client_id,
            client_secret=settings.keycloak_client_secret,
            default_role=settings.keycloak_default_role,
            public_url=settings.keycloak_public_url,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            # Пропускаем миграции в тестовом режиме
            if not settings.db_name.endswith("_test"):
                run_migrations(settings)
            async with db_manager.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            yield
        finally:
            await db_manager.dispose()
            await keycloak_client.close()

    app = FastAPI(title="Web LLM", lifespan=lifespan)

    # CORS-middleware добавляется до роутеров и перехватывает preflight (OPTIONS),
    # иначе браузер блокирует cross-origin запросы фронтенда с 405
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = settings
    app.state.db_manager = db_manager
    app.state.keycloak_client = keycloak_client

    setup_exception_handlers(app)

    container = make_async_container(
        AppProvider(),
        # Штатные Settings/DatabaseManager/KeycloakClient из create_app пробрасываются в контейнер,
        # чтобы DI не пересоздавал их из окружения/.env (иначе в тестах БД указывала бы не туда)
        context={
            Settings: settings,
            DatabaseManager: db_manager,
            KeycloakClientProtocol: keycloak_client,
        },
    )
    setup_dishka(container, app)

    from app.presentation_layer.controllers import router

    app.include_router(router)

    return app
