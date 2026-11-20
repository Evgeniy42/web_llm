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
    # Origin'ы, которым разрешены cross-origin запросы:
    # 5173 — dev-сервер Vite, 8090 — фронтенд в Docker
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:8090"]
    # Адрес фронтенда: callback входа редиректит браузер сюда после создания сессии
    frontend_url: str = "http://localhost:5173"
    # Keycloak: хранит пароли и роли, доступен только серверной части
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "web-llm"
    keycloak_client_id: str = "web-llm-backend"
    # Секрет клиента Keycloak: обязателен, дефолта нет — задаётся через окружение/.env
    keycloak_client_secret: str
    # Аудитория Web LLM API: backend принимает только JWT с этим значением в claim aud
    # (добавляется client scope'ом web-llm-api в realm, см. keycloak/realm-web-llm.json)
    keycloak_api_audience: str = "web-llm-api"
    # Публичный адрес Keycloak, доступный браузеру (редирект на страницу входа).
    # Отличается от keycloak_url: backend ходит в Keycloak по внутренней docker-сети
    keycloak_public_url: str = "http://localhost:8080"
    # Единый callback backend'а, куда Keycloak возвращает браузер после входа
    # (форма Keycloak и Google); должен быть в Valid Redirect URIs клиента Keycloak
    keycloak_redirect_uri: str = "http://localhost:8000/api/v1/user/login/callback"
    # Alias identity provider'а Google в Keycloak (kc_idp_hint)
    google_idp_alias: str = "google"
    # Embedding-сервис (llama.cpp): OpenAI-совместимый /v1/embeddings.
    # Для app в docker-compose переопределяется на http://embeddings:8080
    embedding_url: str = "http://localhost:8081"
    # Имя модели в alias llama-server (поле model в запросе /v1/embeddings)
    embedding_model: str = "qwen3-embedding-0.6b"
    # Размерность вектора Qwen3-Embedding-0.6B: используется при создании
    # коллекции в Qdrant (этап 2) и для самопроверки ответа сервиса
    embedding_dim: int = 1024
