import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.configuration.application_factory import create_app
from app.configuration.settings import Settings
from tests.config import IntegrationTestSettings


@pytest.fixture(scope="session")
def test_settings() -> IntegrationTestSettings:
    return IntegrationTestSettings()


@pytest.fixture(scope="session")
def app(test_settings):
    settings = Settings(
        database_url=test_settings.database_url.get_secret_value(),
        db_user="test",
        db_password="test",
        db_name="web_llm_test",
        db_host="localhost",
        db_port=5432,
    )
    application = create_app(settings)
    yield application
    application.state.db_manager.dispose()


@pytest.fixture(scope="function")
def db_session(app):
    """Создаёт сессию с откатом транзакции после каждого теста."""
    engine = app.state.db_manager.engine
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(app, db_session):
    """HTTP-клиент с подменой сессии БД на тестовую."""
    from app.presentation_layer.routers.user_router import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
