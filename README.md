# Web LLM

Веб-приложение для чата с LLM-моделью (в данный момент — заглушка с 10 случайными ответами).

## Стек

- **Backend:** FastAPI, SQLAlchemy 2.x, Advanced Alchemy, Pydantic 2.x
- **База данных:** PostgreSQL 16
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

Поднимаются четыре сервиса: `db` (PostgreSQL приложения), `keycloak-db` (PostgreSQL Keycloak), `keycloak` (с импортом realm `web-llm` из `keycloak/realm-web-llm.json`) и `app` — backend стартует только после готовности Keycloak.

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

## Тестирование

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
├── across_layers/          # Общие сущности (Entity)
│   └── entities/
├── application_layer/      # Бизнес-логика
│   ├── contracts/          # Protocol-контракты репозиториев
│   ├── services/           # Сервисы приложения
│   └── utils/              # Утилиты (хеширование)
├── configuration/          # Настройки, DI, фабрика приложения
│   ├── application_factory.py
│   ├── database.py
│   └── settings.py
├── data_access_layer/      # Доступ к данным
│   ├── models/             # ORM-модели
│   ├── repositories/       # Реализации репозиториев
│   ├── mappers/            # Преобразование ORM → Entity
│   └── keycloak_client.py  # HTTP-клиент Keycloak (Admin API + OIDC token)
├── migrations/sql/         # SQL-миграции Flyway
└── presentation_layer/     # HTTP-слой
    ├── dto/                # Pydantic DTO
    ├── dependencies/       # Зависимости FastAPI (аутентификация по cookie/Bearer JWT, RBAC)
    └── routers/            # FastAPI роутеры
```

Аутентификация (Keycloak):

- Realm `web-llm`, роли `user`/`vip_user`/`admin` и клиент `web-llm-backend` описаны в `keycloak/realm-web-llm.json` и импортируются при старте контейнера; секреты подставляются из переменных окружения (плейсхолдеры `${...}`).
- Пароли и роли хранятся только в Keycloak; таблица `user` хранит профиль и `keycloak_id` (уникальный, поиск профиля — по `sub` из JWT).
- Вход — authorization code flow + PKCE через страницу Keycloak; сессия — HttpOnly-cookie `access_token`/`refresh_token`. `Authorization: Bearer` тоже поддерживается (совместимость, тесты).
- JWT валидируется строго: подпись RS256 по JWKS, аудитория `web-llm-api` (audience-маппер на клиенте `web-llm-backend` в realm — не client scope: импорт realm с собственной секцией `clientScopes` подавляет встроенные scope'ы `openid`/`profile`/`email` и ломает логин), тип `typ=Bearer`, обязательные claims `exp`/`iat`/`sub`, issuer.

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
| POST | `/chat/send` | Отправка сообщения в чат; требует сессию с ролью `vip_user` или `admin` |

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
