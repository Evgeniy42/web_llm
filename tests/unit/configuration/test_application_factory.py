from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.configuration.application_factory import create_app
from app.configuration.settings import Settings


@pytest.fixture
def test_settings():
    return Settings(
        database_url="postgresql+psycopg://test:test@localhost:5432/web_llm_test",
        db_user="test",
        db_password="test",
        db_name="web_llm_test",
        db_host="localhost",
        db_port=5432,
    )


class TestCreateApp:
    def test_app_created_with_settings(self, test_settings):
        with patch(
            "app.configuration.application_factory.run_migrations"
        ) as mock_migrations, patch(
            "app.configuration.application_factory.DatabaseManager"
        ) as mock_db_manager:
            mock_engine = MagicMock()
            mock_db_manager.return_value.engine = mock_engine

            app = create_app(test_settings)

            assert app.title == "Web LLM"
            assert app.state.settings == test_settings

            with TestClient(app):
                mock_migrations.assert_called_once_with(test_settings)

    def test_lifespan_runs_migrations(self, test_settings):
        with patch(
            "app.configuration.application_factory.run_migrations"
        ) as mock_migrations, patch(
            "app.configuration.application_factory.DatabaseManager"
        ) as mock_db_manager:
            mock_engine = MagicMock()
            mock_db_manager.return_value.engine = mock_engine

            app = create_app(test_settings)

            with TestClient(app) as client:
                assert client.get("/health").status_code == 200
                mock_migrations.assert_called_once()

    def test_lifespan_fails_on_migration_error(self, test_settings):
        with patch(
            "app.configuration.application_factory.run_migrations",
            side_effect=RuntimeError("Flyway migration failed"),
        ), patch(
            "app.configuration.application_factory.DatabaseManager"
        ) as mock_db_manager:
            mock_engine = MagicMock()
            mock_db_manager.return_value.engine = mock_engine

            app = create_app(test_settings)

            with pytest.raises(RuntimeError, match="Flyway migration failed"), TestClient(app):
                pass
