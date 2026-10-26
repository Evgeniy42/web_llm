import subprocess

import pytest
from sqlalchemy import create_engine, text

from tests.config import IntegrationTestSettings


@pytest.fixture(scope="module")
def test_settings():
    return IntegrationTestSettings()


def _run_flyway(settings: IntegrationTestSettings) -> subprocess.CompletedProcess:
    url = settings.database_url.get_secret_value()
    # postgresql+psycopg_async://user:pass@host:port/db → jdbc:postgresql://host:port/db
    jdbc_url = url.replace("postgresql+psycopg_async://", "jdbc:postgresql://")
    # убираем credentials из URL
    parts = jdbc_url.split("@")
    if len(parts) == 2:
        jdbc_url = "jdbc:postgresql://" + parts[1]

    return subprocess.run(
        [
            "flyway", "migrate",
            f"-url={jdbc_url}",
            "-user=web_llm_test",
            "-password=web_llm_test",
            "-locations=filesystem:./app/migrations/sql",
        ],
        capture_output=True,
        text=True,
    )


class TestMigrations:
    def test_flyway_creates_schema(self, test_settings):
        result = _run_flyway(test_settings)
        assert result.returncode == 0, f"Flyway failed: {result.stderr or result.stdout}"

        engine = create_engine(test_settings.database_url.get_secret_value())
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
        result = _run_flyway(test_settings)
        assert result.returncode == 0

    def test_user_table_columns(self, test_settings):
        engine = create_engine(test_settings.database_url.get_secret_value())
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
        engine = create_engine(test_settings.database_url.get_secret_value())
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT indexname FROM pg_indexes WHERE tablename='user'"
            ))
            indexes = [row[0] for row in result]
            assert "idx_user_email" in indexes
            assert "idx_user_username" not in indexes
        engine.dispose()
