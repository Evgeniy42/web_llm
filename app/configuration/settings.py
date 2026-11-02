from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    db_user: str = "web_llm"
    db_password: str = "web_llm"
    db_name: str = "web_llm"
    db_host: str = "localhost"
    db_port: int = 5432
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # Origin'ы, которым разрешены cross-origin запросы (dev-сервер Vite)
    allowed_origins: list[str] = ["http://localhost:5173"]
