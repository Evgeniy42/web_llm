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
Админ-консоль Keycloak: `http://localhost:8080/admin` (логин/пароль — `KEYCLOAK_ADMIN`/`KEYCLOAK_ADMIN_PASSWORD` из `.env`).

Регистрация и вход идут через backend: он создаёт пользователя и проверяет пароль в Keycloak, а клиенту возвращает JWT сессии. Клиент с Keycloak напрямую не общается.

### Вход через Google

Google подключён как Identity Provider в Keycloak (см. `identityProviders` в `keycloak/realm-web-llm.json`). Кнопка «Войти через Google» на клиенте — обычная ссылка на `GET /user/login/google`: браузер уходит в Keycloak → Google и возвращается на `GET /user/login/google/callback` с кодом, backend обменивает его на токены и делает 302-редирект на фронтенд: `{FRONTEND_URL}/auth/callback#access_token=...&refresh_token=...&token_type=Bearer&expires_in=...` (при ошибке — `#error=...`). Токены передаются во fragment, поэтому не попадают в access-логи и на сервер фронтенда. Профиль вошедшего пользователя фронтенд получает через `GET /user/me` с заголовком `Authorization: Bearer <access_token>`.

Настройка:

1. В [Google Cloud Console](https://console.cloud.google.com/) создайте OAuth client (тип Web application) и в Authorized redirect URIs укажите `http://localhost:8080/realms/web-llm/broker/google/endpoint` (порт — `KEYCLOAK_PORT`).
2. Client ID и Client Secret внесите в `identityProviders` в `keycloak/realm-web-llm.json` (или через админ-консоль: realm `web-llm` → Identity Providers → Google).
3. Realm импортируется только при первом старте контейнера с пустой `keycloak-db`. Если realm уже существует, примените изменения в админ-консоли вручную (Standard flow + redirect URI у клиента, роль `user` в Default roles) либо пересоздайте volume: `docker compose down -v && docker compose up --build`.

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
    ├── dependencies/       # Зависимости FastAPI (аутентификация по Bearer JWT, RBAC)
    └── routers/            # FastAPI роутеры
```

Аутентификация (Keycloak):

- Realm `web-llm`, роли `user`/`vip_user`/`admin` и клиент `web-llm-backend` описаны в `keycloak/realm-web-llm.json` и импортируются при старте контейнера.
- Пароли и роли хранятся только в Keycloak; таблица `user` хранит профиль и `keycloak_id`.
- `POST /user/login` возвращает JWT сессии (`access_token`, `refresh_token`, `expires_in`), выпущенный Keycloak.

## API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | Проверка жизни процесса |
| GET | `/health/ready` | Проверка готовности (включая БД) |
| POST | `/user/register` | Регистрация пользователя (в Keycloak); сразу возвращает JWT сессии |
| POST | `/user/login` | Вход; возвращает JWT сессии, выпущенный Keycloak |
| GET | `/user/login/google` | Точка входа для кнопки «Войти через Google»: 302 на страницу входа Google (через Keycloak) |
| GET | `/user/login/google/callback` | Callback от Keycloak: обмен кода на JWT и 302-редирект на фронтенд (`{FRONTEND_URL}/auth/callback`) с токенами или ошибкой во fragment; при первом входе создаёт локальный профиль |
| POST | `/user/logout` | Выход из сессии; отзывает refresh-токен в Keycloak |
| POST | `/user/subscription` | Оформление подписки (имитация): назначает роль `vip_user`; требует Bearer-токен |
| GET | `/user/me` | Профиль текущего пользователя (по email из Bearer JWT) |
| GET | `/user/{id}` | Получение пользователя |
| POST | `/chat/send` | Отправка сообщения в чат; требует Bearer-токен с ролью `vip_user` или `admin` |

## RBAC

Роли хранятся в Keycloak (realm `web-llm`): `user` — без подписки, `vip_user` — с подпиской, `admin` — администратор.
Backend валидирует JWT из заголовка `Authorization: Bearer` (подпись RS256 по JWKS realm'а, issuer, срок действия) и читает роли из claim `realm_access.roles`:

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
