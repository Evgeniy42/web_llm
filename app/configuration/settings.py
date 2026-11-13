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
    # Адрес фронтенда: callback входа через Google редиректит браузер сюда с токенами
    frontend_url: str = "http://localhost:5173"
    # Keycloak: хранит пароли и роли, доступен только серверной части
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "web-llm"
    keycloak_client_id: str = "web-llm-backend"
    keycloak_client_secret: str = "web-llm-backend-secret"
    # Realm-роль Keycloak, назначаемая при регистрации
    keycloak_default_role: str = "user"
    # Публичный адрес Keycloak, доступный браузеру (редирект на страницу входа).
    # Отличается от keycloak_url: backend ходит в Keycloak по внутренней docker-сети
    keycloak_public_url: str = "http://localhost:8080"
    # Эндпоинт backend'а, куда Keycloak возвращает браузер после входа через Google;
    # должен быть в Valid Redirect URIs клиента Keycloak
    google_redirect_uri: str = "http://localhost:8000/api/v1/user/login/google/callback"
    # Alias identity provider'а Google в Keycloak (kc_idp_hint)
    google_idp_alias: str = "google"
