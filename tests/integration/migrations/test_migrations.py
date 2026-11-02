from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from tests.config import IntegrationTestSettings
from tests.integration.conftest import run_flyway


def _sync_engine(test_settings: IntegrationTestSettings):
    """Синхронный engine: драйвер psycopg_async заменяется на синхронный psycopg."""
    url = make_url(test_settings.database_url.get_secret_value())
    sync_url = url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    return create_engine(sync_url)


class TestMigrations:
    def test_flyway_creates_schema(self, test_settings):
        result = run_flyway(test_settings)
        assert result.returncode == 0, f"Flyway failed: {result.stderr or result.stdout}"

        engine = _sync_engine(test_settings)
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            ))
            tables = [row[0] for row in result]
            assert "user" in tables
            assert "flyway_schema_history" in tables
        engine.dispose()

    def test_flyway_idempotent(self, test_settings):
        """Повторный запуск flyway не должен падать."""
        result = run_flyway(test_settings)
        assert result.returncode == 0

    def test_user_table_columns(self, test_settings):
        engine = _sync_engine(test_settings)
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT column_name, data_type, character_maximum_length, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name='user' ORDER BY ordinal_position"
            ))
            columns = {row[0]: row for row in result}

            assert "id" in columns
            assert "username" in columns
            assert "email" in columns
            assert "password" in columns

            assert columns["username"][2] == 50  # VARCHAR(50)
            assert columns["email"][2] == 255  # VARCHAR(255)
            assert columns["username"][3] == "NO"  # NOT NULL
        engine.dispose()

    def test_user_table_unique_constraints(self, test_settings):
        engine = _sync_engine(test_settings)
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT indexname FROM pg_indexes WHERE tablename='user'"
            ))
            indexes = [row[0] for row in result]
            assert "idx_user_email" in indexes
            assert "idx_user_username" not in indexes
        engine.dispose()
