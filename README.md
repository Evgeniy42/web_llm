# Web LLM

Веб-приложение: чат с LLM по загруженным документам (RAG). Пользователь задаёт вопрос — backend ищет релевантные фрагменты в векторной базе, собирает из них системный промпт и отвечает через генеративную модель с указанием источников.

## RAG-пайплайн

```
загрузка документа (POST /api/v1/rag/embed, только admin)
  → docling-service: файл → Markdown
  → MarkdownChunker: Markdown → чанки (границы по токенам модели)
  → Qwen3-Embedding: чанки → векторы 1024-мерные (L2-нормализованные)
  → Qdrant: upsert чанков (doc_id + chunk_index, идемпотентно)

вопрос в чат (POST /api/v1/chat/send, роль vip_user/admin)
  → RetrievalService: вопрос → эмбеддинг → векторный поиск top-k
  → rag_prompt.py: системный промпт с найденными чанками
  → OpenAI API: ответ с опорой на контекст и источники
```

## Стек

- **Backend:** FastAPI, SQLAlchemy 2.x, dishka (DI), Pydantic 2.x
- **База данных:** PostgreSQL 16 (профили пользователей)
- **Векторная БД:** Qdrant (коллекция `rag_chunks`, cosine, вектор 1024)
- **Эмбеддинг-сервис:** llama.cpp server (`server-cuda`) с Qwen3-Embedding-0.6B (GGUF) (Или замена на любую другую модель по пути `rag\emb_models`)
- **LLM:** OpenAI API
- **Конвертация документов:** docling 2.151 (микросервис `docling-service`: PDF/DOCX/XLSX/PNG → Markdown, CPU + RapidOCR)
- **Аутентификация:** Keycloak 26 (пароли и роли пользователей; backend обращается к нему по Admin REST API и OIDC)
- **Миграции:** Flyway
- **CI/CD:** Docker Compose
- **Frontend** React

## Frontend часть
Расположена в репозитории https://github.com/Evgeniy42/web_llm_frontend

## Быстрый старт

### 1. Клонирование и установка

```bash
git clone <repo>
cd web-llm
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Настройка окружения

```bash
cp .env.example .env
# Отредактируйте .env при необходимости
```

### 3. Запуск через Docker Compose

```bash
docker compose up --build
```

Поднимаются семь сервисов: `db` (PostgreSQL приложения), `keycloak-db` (PostgreSQL Keycloak), `keycloak` (с импортом realm `web-llm` из `keycloak/realm-web-llm.json`), `qdrant` (векторная БД), `embeddings` (llama.cpp server с моделью эмбеддингов), `docling-service` (конвертация документов) и `app` — backend стартует только после готовности зависимостей.


Приложение будет доступно по адресу `http://localhost:8000`.
Документация API: `http://localhost:8000/docs`.
Админ-консоль Keycloak: `http://localhost:8080/admin` (логин/пароль — `KEYCLOAK_ADMIN`/`KEYCLOAK_ADMIN_PASSWORD` из `.env`; порт опубликован только на loopback).

Регистрация и вход идут через страницу Keycloak: backend перенаправляет браузер на форму логина/регистрации Keycloak (authorization code flow + PKCE), а после входа создаёт сессию в HttpOnly-cookie. Пароли через backend не проходят, токены не попадают в URL и в JS фронтенда.

### Вход и регистрация

Кнопки «Войти» и «Войти через Google» на клиенте — обычные ссылки:

1. `GET /api/v1/user/login` → 302 на страницу логина Keycloak (логин/пароль, там же ссылка на регистрацию).
2. `GET /api/v1/user/login/google` → то же, но с `kc_idp_hint=google` — сразу форма Google.
3. После входа Keycloak возвращает браузер на `GET /api/v1/user/login/callback` с кодом; backend проверяет `state`, обменивает код на токены (с PKCE-verifier из cookie), валидирует JWT, при первом входе создаёт локальный профиль и устанавливает сессионные cookie `access_token` и `refresh_token` (HttpOnly, SameSite=Lax).
4. Браузер получает 302 на `{FRONTEND_URL}/auth/callback`: при успехе без параметров, при ошибке — с `#error=...`. Профиль и роли фронтенд получает через `GET /api/v1/user/me` (сессия определяется по cookie).

Настройка Google-входа:

1. В [Google Cloud Console](https://console.cloud.google.com/) создайте OAuth client (тип Web application) и в Authorized redirect URIs укажите `http://localhost:8080/realms/web-llm/broker/google/endpoint` (порт — `KEYCLOAK_PORT`).
2. Client ID и Client Secret задайте в `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`) — они подставляются в realm при импорте через плейсхолдеры `${...}` в `keycloak/realm-web-llm.json` (включается `JAVA_OPTS_APPEND=-Dkeycloak.migration.replace-placeholders=true` в docker-compose). Секреты в JSON не хранятся. Существующий realm можно обновить и через админ-консоль: realm `web-llm` → Identity Providers → Google.
3. Realm импортируется только при первом старте контейнера с пустой `keycloak-db`: на существующей БД повторный импорт не срабатывает. Чтобы применить изменения `realm-web-llm.json` без потери данных приложения, обновите настройки в админ-консоли вручную либо пересоздайте ТОЛЬКО том Keycloak:

```bash
docker compose rm -sf keycloak keycloak-db
docker volume rm web-llm_keycloak_postgres_data  # имя тома: docker volume ls
docker compose up --build
```

`docker compose down -v` для этого НЕ используйте: он удалит и том PostgreSQL приложения.

### 4. Локальный запуск (без Docker)

```bash
# Запустите PostgreSQL локально или через Compose:
docker compose up db -d

# Запустите Keycloak (для регистрации/входа он обязателен):
docker compose up keycloak -d

# Запустите приложение:
python main.py
```

## Запуск из IDE (PyCharm)

1. **Интерпретатор:** выберите `.venv` (созданный выше)
2. **Точка входа:** `main.py`
3. **Рабочая папка:** корень проекта
4. **Подключение к БД:** Database → PostgreSQL → `localhost:5432`, user/password из `.env`

### Unit-тесты (без PostgreSQL)

```bash
pytest tests/unit -v
```

### Интеграционные тесты (требуют PostgreSQL)

Keycloak в интеграционных тестах заменён in-memory заглушкой (`MockKeycloakClient` в `tests/resources/mocks.py`), поднимать контейнер Keycloak не нужно.

```bash
# Запустите тестовую PostgreSQL:
docker compose -f docker-compose.test.yml up -d

# Создайте .env.test:
cp .env.test.example .env.test

# Запустите тесты:
pytest tests/integration -v
```

## Миграции

Миграции выполняются автоматически при запуске приложения (в `lifespan` FastAPI).

Для ручного запуска:

```bash
flyway migrate \
  -url=jdbc:postgresql://localhost:5432/web_llm \
  -user=web_llm \
  -password=web_llm \
  -locations=filesystem:./app/migrations/sql
```

Новая миграция: создайте файл `V4__description.sql` в `app/migrations/sql/`.

## Архитектура

```
app/
├── across_layers/          # Общие сущности (Entity): чанки, пользователи, токены
│   └── entities/
├── application_layer/      # Бизнес-логика
│   ├── contracts/
│   │   ├── client_contracts/   # Контракты сторонних решений (docling, embedding,
│   │   │                       #   keycloak, llm, qdrant)
│   │   └── service_contracts/  # Внутренние контракты (tokenizer, user_repository)
│   ├── prompts/            # Шаблоны промптов (rag_prompt.py)
│   ├── services/           # Сервисы: chat, embedding, retrieval, chunker, user
│   └── utils/              # Утилиты (хеширование)
├── configuration/          # Настройки, DI (dishka), фабрика приложения
│   ├── application_factory.py
│   ├── container.py
│   ├── database.py
│   └── settings.py
├── data_access_layer/      # Доступ к данным
│   ├── clients/            # HTTP-клиенты внешних систем: keycloak_client,
│   │                       #   embedding_client, llm_client, docling_client, qdrant_store
│   ├── models/             # ORM-модели
│   ├── repositories/       # Реализации репозиториев + mock_llm (тестовый дабл)
│   └── mappers/            # Преобразование ORM → Entity
├── migrations/sql/         # SQL-миграции Flyway
└── presentation_layer/     # HTTP-слой
    ├── dto/                # Pydantic DTO
    ├── dependencies/       # Зависимости FastAPI (аутентификация по cookie/Bearer JWT, RBAC)
    ├── controllers/        # FastAPI роутеры
    └── handlers/           # Обработчики исключений → коды ответов

docling-service/            # Внутренний микросервис конвертации (отдельный образ)
├── controllers/            # Тонкий HTTP-слой (роутеры /health, /convert)
└── service/                # DoclingService + ленивый синглтон get_conversion_service()
```

Аутентификация (Keycloak):

- Realm `web-llm`, роли `user`/`vip_user`/`admin` и клиент `web-llm-backend` описаны в `keycloak/realm-web-llm.json` и импортируются при старте контейнера; секреты подставляются из переменных окружения (плейсхолдеры `${...}`).
- Пароли и роли хранятся только в Keycloak; таблица `user` хранит профиль и `keycloak_id` (уникальный, поиск профиля — по `sub` из JWT).
- Вход — authorization code flow + PKCE через страницу Keycloak; сессия — HttpOnly-cookie `access_token`/`refresh_token`. `Authorization: Bearer` тоже поддерживается (совместимость, тесты).
- JWT валидируется строго: подпись RS256 по JWKS, аудитория `web-llm-api` (audience-маппер на клиенте `web-llm-backend` в realm — не client scope: импорт realm с собственной секцией `clientScopes` подавляет встроенные scope'ы `openid`/`profile`/`email` и ломает логин), тип `typ=Bearer`, обязательные claims `exp`/`iat`/`sub`, issuer.

## RAG: модели и как их менять

### Используемые модели

| Назначение | Модель | Как подключена |
|---|---|---|
| Эмбеддинги | **Qwen3-Embedding-0.6B** (GGUF Q4_K_M, `rag/emb_models/`) | llama.cpp server (`server-cuda`), флаги `--embeddings --pooling last`, вектор 1024, L2-нормализация |
| Генерация ответов | **~z-ai/glm-latest** | OpenAI API, ключ `LLM_API_KEY` |
| Конвертация документов | **docling 2.151** | отдельный микросервис (CPU, torch), веса layout/таблиц/OCR кешируются в volume `web_llm_docling_models` |

### Замена эмбеддинг-модели

1. Положите новый GGUF в `rag/emb_models/` и поправьте путь в `docker-compose.yml` (сервис `embeddings`, аргумент `--model`).
2. Обновите настройки в `.env`: `EMBEDDING_MODEL` (alias модели), `EMBEDDING_DIM` (размерность).
3. ⚠️ **Векторные пространства моделей несовместимы**: после смены модели все ранее загруженные документы нужно загрузить заново (`POST /api/v1/rag/embed` идемпотентен, повторная загрузка перезапишет чанки).
4. ⚠️ Смена `EMBEDDING_DIM` требует пересоздания коллекции Qdrant: `docker compose rm -sf qdrant && docker volume rm web-llm_qdrant_data && docker compose up -d` (удалит все чанки).
5. Пулинг зависит от модели: для Qwen3-Embedding обязателен `--pooling last`, у других моделей флаг может отличаться — смотрите документацию llama.cpp.

### Стратегия чанкирования (`app/application_layer/services/markdown_chunker.py`)

Markdown нарезается структурно, счёт токенов ведёт **настоящий токенайзер эмбеддинг-модели** (`/tokenize` llama-server) — границы чанков совпадают с тем, как модель «видит» текст:

1. Markdown → структурные блоки (заголовок, абзац; кодовый fence атомарен, не режется).
2. Блоки → токены пакетно.
3. Жадная сборка чанков до `max_tokens`; резка только между блоками. `min_tokens` — цель, а не гарантия: короткий раздел не растягивается чужим текстом.
4. Блок больше `max_tokens` → сплит сначала по предложениям; предложение длиннее `max_tokens` → скользящее окно по токенам.
5. Overlap `rag_chunk_overlap_ratio` (по умолчанию **0.12**, 12% от длины предыдущего чанка): хвост чанка переносится в начало следующего с резкой по границе предложения; если не влезает — ужимается вплоть до нуля.

Настройки (`.env`): `RAG_CHUNK_MIN_TOKENS=300`, `RAG_CHUNK_MAX_TOKENS=800`, `RAG_CHUNK_OVERLAP_RATIO=0.12`.

### Стратегия поиска (`app/application_layer/services/retrieval_service.py`)

- Вопрос векторизуется **той же моделью**, что и чанки (`embed_one`) — запрос и документы в одном векторном пространстве.
- Поиск: Qdrant `query_points`, метрика **cosine** (векторы нормализованы), `top_k = RAG_SEARCH_TOP_K` (по умолчанию **5**).
- Опциональный фильтр `doc_id` — поиск внутри одного документа (Qdrant применяет фильтр во время обхода HNSW-индекса, не пост-обработкой).
- Порог отсечения по score **не применяется**: все top-k чанки попадают в системный промпт (`app/application_layer/prompts/rag_prompt.py`), модель сама опирается на релевантное и обязана честно отказаться, если ответа нет в контексте.

## API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | Проверка жизни процесса |
| GET | `/health/ready` | Проверка готовности (включая БД) |
| GET | `/user/login` | 302 на страницу логина Keycloak (логин/пароль, ссылка на регистрацию); state и PKCE-verifier — в HttpOnly-cookie |
| GET | `/user/login/google` | То же, но с `kc_idp_hint=google`: сразу форма входа Google |
| GET | `/user/login/callback` | Единый callback от Keycloak: обмен кода на токены (PKCE), создание локального профиля при первом входе, сессионные cookie и 302 на `{FRONTEND_URL}/auth/callback` (при ошибке — `#error=...`) |
| POST | `/user/logout` | Выход из сессии: отзывает refresh-токен (из cookie) в Keycloak и очищает cookie; всегда 204 |
| POST | `/user/subscription` | Оформление подписки (имитация): назначает роль `vip_user`; требует сессию |
| GET | `/user/me` | Профиль текущего пользователя и его роли: `{id, username, email, roles}`; 401 без валидной сессии |
| POST | `/chat/send` | Отправка сообщения в чат (RAG: поиск чанков → промпт → LLM); требует сессию с ролью `vip_user` или `admin` |
| POST | `/rag/embed` | Загрузка документа в векторную базу (конвертация → чанкинг → эмбеддинги → Qdrant); **только admin**. Идемпотентна: повторная загрузка того же `doc_id` перезаписывает чанки |

## RBAC

Роли хранятся в Keycloak (realm `web-llm`): `user` — без подписки, `vip_user` — с подпиской, `admin` — администратор.
Backend валидирует JWT из cookie `access_token` или заголовка `Authorization: Bearer` (подпись RS256 по JWKS realm'а, аудитория, issuer, срок действия) и читает роли из claim `realm_access.roles`:

- `/chat/send` доступен ролям `vip_user` и `admin`. Пользователь с ролью `user` получает `200` с сообщением чата «У вас нет подписки. Доступ к чату запрещен.» — фронтенд показывает его в диалоге.
- `/user/subscription` — имитация оплаты подписки: назначает роль `vip_user` текущему пользователю (по `sub` из JWT). Роль попадёт в токен только после повторного входа — роли зашиты в выданный JWT снимком.

## Проверки качества

```bash
# Линтер
ruff check .

# Типизация
mypy app/

# Все тесты
pytest
```
