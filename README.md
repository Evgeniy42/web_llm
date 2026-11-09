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
    └── routers/            # FastAPI роутеры
```

Аутентификация (Keycloak):

- Realm `web-llm`, роли `user`/`admin` и клиент `web-llm-backend` описаны в `keycloak/realm-web-llm.json` и импортируются при старте контейнера.
- Пароли и роли хранятся только в Keycloak; таблица `user` хранит профиль и `keycloak_id`.
- `POST /user/login` возвращает JWT сессии (`access_token`, `refresh_token`, `expires_in`), выпущенный Keycloak.

## API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | Проверка жизни процесса |
| GET | `/health/ready` | Проверка готовности (включая БД) |
| POST | `/user/register` | Регистрация пользователя (в Keycloak); сразу возвращает JWT сессии |
| POST | `/user/login` | Вход; возвращает JWT сессии, выпущенный Keycloak |
| POST | `/user/logout` | Выход из сессии; отзывает refresh-токен в Keycloak |
| GET | `/user/{id}` | Получение пользователя |
| POST | `/chat/send` | Отправка сообщения в чат |

## Проверки качества

```bash
# Линтер
ruff check .

# Типизация
mypy app/

# Все тесты
pytest
```
