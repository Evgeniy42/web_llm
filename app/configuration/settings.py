from pydantic import Field, model_validator
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
    # Qdrant (REST API). Для app в docker-compose переопределяется на http://qdrant:6333
    qdrant_url: str = "http://localhost:6333"
    # Имя коллекции чанков документов
    qdrant_collection: str = "rag_chunks"
    # Внутренний микросервис конвертации документов (docling-service).
    # Порт не публикуется наружу; в docker-compose переопределяется на
    # http://docling-service:8082
    docling_service_url: str = "http://localhost:8082"
    # Чанкинг Markdown (этап 4). Токены считает настоящий токенайзер модели
    # (/tokenize llama-server), поэтому min/max — в токенах модели.
    # min_tokens — цель (короткий раздел не растягивается чужим текстом),
    # max_tokens — жёсткий предел. overlap_ratio — перекрытие соседних
    # чанков, доля от длины предыдущего чанка (плановые 10–15%).
    rag_chunk_min_tokens: int = Field(default=300, ge=50)
    rag_chunk_max_tokens: int = Field(default=800, ge=100)
    rag_chunk_overlap_ratio: float = Field(default=0.12, gt=0.0, le=0.5)
    # Векторный поиск чанков (этап 5): сколько ближайших чанков берётся
    # в контекст по умолчанию (можно переопределить per-request).
    rag_search_top_k: int = Field(default=5, ge=1, le=50)
    # Генеративная модель (этап 6): OpenAI-совместимый API через туннель AItunnel.
    # Токен берётся из .env (LLM_API_KEY); без него клиент не создаётся —
    # впишите свой токен с https://aitunnel.ru.
    llm_api_key: str = ""
    llm_base_url: str = "https://api.aitunnel.ru/v1/"
    llm_model: str = "~z-ai/glm-latest"

    @model_validator(mode="after")
    def _check_chunk_bounds(self) -> "Settings":
        if self.rag_chunk_min_tokens >= self.rag_chunk_max_tokens:
            raise ValueError("rag_chunk_min_tokens должно быть меньше rag_chunk_max_tokens")
        return self
