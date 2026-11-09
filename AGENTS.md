# Веб-приложения для чата с LLM-моделью

### Краткое описание
Fullstack-приложение для чата с LLM. Backend: сервис пользователя (регистрация, вход,
получение по ID) и минимальный сценарий чата (10 случайных ответов вместо LLM).
Регистрация и аутентификация — через Keycloak (пароли и роли хранятся там,
backend отдаёт клиенту JWT сессии). Frontend: React-приложение для веб-интерфейса чата.

### Стек
- CI/CD: Docker Compose
- Backend: FastAPI, SQLAlchemy 2.x, Pydantic 2.x, PostgreSQL 16
- Auth: Keycloak 26 (realm `web-llm` импортируется из `keycloak/realm-web-llm.json`;
  отдельная PostgreSQL `keycloak-db`; доступ только с backend)
- Frontend: React 19, Vite, oxlint
- Migration: Flyway (выполняется при старте приложения)
- Тесты: pytest (unit + integration с настоящей PostgreSQL; Keycloak заменён моком)

### Архитектура backend
- `across_layers/entities` — внутренние сущности (UserEntity, TokenInfo)
- `application_layer/` — бизнес-логика (сервисы, контракты: UserRepositoryProtocol, KeycloakClientProtocol)
- `configuration/` — настройки, фабрика приложения, DatabaseManager
- `data_access_layer/` — ORM-модели, репозитории, мапперы, `keycloak_client.py` (Admin REST API + OIDC)
- `presentation_layer/` — DTO, роутеры
- `migrations/sql/` — SQL-миграции Flyway

### Архитектура frontend (`frontend/web-llm/src`)
- `components/` — переиспользуемые React-компоненты
- `hooks/` — кастомные React-хуки
- `pages/` — страницы приложения
- `services/` — работа с API (запросы к backend)
- `utils/` — вспомогательные функции
- `assets/` — статические ресурсы (изображения, иконки)
- `App.jsx` — корневой компонент
- `main.jsx` — точка входа

### Сервисы
- UserService — регистрация и вход через Keycloak (пароль уходит только в Keycloak,
  в локальной БД — профиль и `keycloak_id`), получение пользователя;
  register/login возвращают `AuthResult` (UserEntity + TokenInfo с JWT от Keycloak),
  logout отзывает refresh-токен в Keycloak
- ChatService — отправка сообщений (MockLLM с 10 случайными ответами)

### Тесты (`tests/`)
- `unit/` — юнит-тесты без внешних зависимостей; структура повторяет слои приложения:
  `application_layer/`, `configuration/` (async-тесты, `asyncio_mode = "auto"`)
- `integration/` — тесты с настоящей PostgreSQL (только через `docker-compose.test.yml`);
  структура по слоям: `presentation_layer/`, `data_access_layer/`, `migrations/`;
  приложение создаётся штатной `create_app` из `app/configuration`, параметры БД — из `TEST_DATABASE_URL`
- `resources/` — общие тестовые данные и константы: `api.py` (пути и ключи JSON),
  `users.py` (пользователи и payload-конструкторы), `mocks.py` (моки и фабрики,
  в т.ч. `MockKeycloakClient` — in-memory заглушка Keycloak для unit- и API-тестов).
  Повторяющиеся значения хранятся здесь, а не в тестах

### Скрипты frontend
- `npm run dev` — запуск dev-сервера Vite
- `npm run build` — сборка для продакшена
- `npm run lint` — проверка кода oxlint
- `npm run preview` — предпросмотр сборки
