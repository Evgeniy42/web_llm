import asyncio
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.configuration.application_factory import create_app
from app.configuration.settings import Settings
from tests.config import IntegrationTestSettings

# На Windows psycopg async требует SelectorEventLoop вместо ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def run_flyway(settings: IntegrationTestSettings) -> subprocess.CompletedProcess:
    """Запускает flyway migrate; параметры подключения берутся из TEST_DATABASE_URL."""
    url = make_url(settings.database_url.get_secret_value())
    jdbc_url = f"jdbc:postgresql://{url.host}:{url.port}/{url.database}"

    return subprocess.run(
        [
            "flyway",
            "migrate",
            f"-url={jdbc_url}",
            f"-user={url.username}",
            f"-password={url.password}",
            "-locations=filesystem:./app/migrations/sql",
        ],
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def test_settings() -> IntegrationTestSettings:
    return IntegrationTestSettings()


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(test_settings):
    """Применяет Flyway-миграции один раз до всех интеграционных тестов.

    Lifespan приложения пропускает миграции для БД с суффиксом _test,
    поэтому схема создаётся явно здесь — порядок прогона тестов значения не имеет.
    """
    result = run_flyway(test_settings)
    assert result.returncode == 0, f"Flyway failed: {result.stderr or result.stdout}"


@pytest.fixture(scope="session")
def app(test_settings):
    """Приложение создаётся штатной фабрикой create_app из app.configuration.

    Все параметры БД (host, port, user, password, name) извлекаются из
    TEST_DATABASE_URL — единый источник, расхождений с docker-compose.test.yml нет.
    """
    url = make_url(test_settings.database_url.get_secret_value())
    settings = Settings(
        database_url=test_settings.database_url.get_secret_value(),
        db_user=url.username or "",
        db_password=url.password or "",
        db_name=url.database or "",
        db_host=url.host or "localhost",
        db_port=url.port or 5432,
    )
    application = create_app(settings)
    yield application


@pytest.fixture(autouse=True)
async def clean_users_table(app):
    """Очищает таблицу user перед каждым тестом.

    API-тесты коммитят данные реальными запросами; без очистки повторная
    регистрация одного и того же TEST_USER_1 соседними тестами давала бы конфликты.
    """
    async with app.state.db_manager.engine.begin() as conn:
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    yield


@pytest.fixture(scope="function")
async def db_session(app) -> AsyncSession:
    """Создаёт асинхронную сессию с откатом транзакции после каждого теста."""
    async with app.state.db_manager.get_session() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture(scope="function")
def client(app):
    """HTTP-клиент для тестирования API."""
    with TestClient(app) as c:
        yield c
