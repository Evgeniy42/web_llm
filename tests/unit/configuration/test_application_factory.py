from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.configuration.application_factory import create_app
from app.configuration.database import DatabaseManager
from app.configuration.settings import Settings
from tests.resources.api import HEALTH_PATH


@pytest.fixture
def test_settings():
    return Settings(
        database_url="postgresql+psycopg://test:test@localhost:5432/web_llm_unit",
        db_user="test",
        db_password="test",
        # не _test: lifespan пропускает миграции для тестовых БД,
        # а здесь проверяется штатный запуск миграций
        db_name="web_llm_unit",
        db_host="localhost",
        db_port=5432,
    )


def _patch_infrastructure(mock_migrations=None):
    """Патчит run_migrations и DatabaseManager; engine — AsyncMock (поддерживает async with/await).

    DatabaseManager патчится через __init__, а не заменой класса: сам класс —
    ключ context DI-контейнера в create_app, его подмена ломает сборку контейнера.
    """
    conn = AsyncMock()  # await conn.execute(...) работает из коробки
    engine = MagicMock()
    engine.connect.return_value.__aenter__.return_value = conn
    engine.connect.return_value.__aexit__.return_value = None

    def fake_init(self, database_url):
        self.engine = engine
        self.dispose = AsyncMock()

    patches = [
        patch("app.configuration.application_factory.run_migrations", mock_migrations),
        patch.object(DatabaseManager, "__init__", fake_init),
    ]
    return patches, engine


class TestCreateApp:
    def test_app_created_with_settings(self, test_settings):
        mock_migrations = MagicMock()
        patches, _ = _patch_infrastructure(mock_migrations)
        with patches[0], patches[1]:
            app = create_app(test_settings)

            assert app.title == "Web LLM"
            assert app.state.settings == test_settings

            with TestClient(app):
                mock_migrations.assert_called_once_with(test_settings)

    def test_lifespan_runs_migrations(self, test_settings):
        mock_migrations = MagicMock()
        patches, _ = _patch_infrastructure(mock_migrations)
        with patches[0], patches[1]:
            app = create_app(test_settings)

            with TestClient(app) as client:
                assert client.get(HEALTH_PATH).status_code == 200
                mock_migrations.assert_called_once()

    def test_lifespan_fails_on_migration_error(self, test_settings):
        patches, _ = _patch_infrastructure(
            MagicMock(side_effect=RuntimeError("Flyway migration failed"))
        )
        with patches[0], patches[1]:
            app = create_app(test_settings)

            with pytest.raises(RuntimeError, match="Flyway migration failed"), TestClient(app):
                pass
