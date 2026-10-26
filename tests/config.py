from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class IntegrationTestSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEST_",
        env_file=PROJECT_ROOT / ".env.test",
        extra="ignore",
    )

    database_url: SecretStr

    @field_validator("database_url")
    @classmethod
    def require_test_postgresql(cls, value: SecretStr) -> SecretStr:
        url = make_url(value.get_secret_value())
        if url.drivername != "postgresql+psycopg" or not (url.database or "").endswith("_test"):
            raise ValueError("A dedicated PostgreSQL database ending in _test is required")
        return value
