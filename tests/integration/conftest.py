import asyncio
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.configuration.application_factory import create_app
from app.configuration.settings import Settings
from tests.config import IntegrationTestSettings

# На Windows psycopg async требует SelectorEventLoop вместо ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session")
def test_settings() -> IntegrationTestSettings:
    return IntegrationTestSettings()


@pytest.fixture(scope="session")
def app(test_settings):
    settings = Settings(
        database_url=test_settings.database_url.get_secret_value(),
        db_user="web_llm_test",
        db_password="web_llm_test",
        db_name="web_llm_test",
        db_host="localhost",
        db_port=55433,
    )
    application = create_app(settings)
    yield application


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
