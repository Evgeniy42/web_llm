# Веб-приложения для чата с LLM-моделью

### Краткое описание
Backend для чата с LLM. Реализованы сервис пользователя (регистрация, вход,
получение по ID) и минимальный сценарий чата (10 случайных ответов вместо LLM).

### Стек
- CI/CD: Docker Compose
- Backend: FastAPI, SQLAlchemy 2.x, Pydantic 2.x, PostgreSQL 16
- Migration: Flyway (выполняется при старте приложения)
- Тесты: pytest (unit + integration с настоящей PostgreSQL)

### Архитектура
- `across_layers/entities` — внутренние сущности (UserEntity)
- `application_layer/` — бизнес-логика (сервисы, контракты, утилиты)
- `configuration/` — настройки, фабрика приложения, DatabaseManager
- `data_access_layer/` — ORM-модели, репозитории, мапперы
- `presentation_layer/` — DTO, роутеры
- `migrations/sql/` — SQL-миграции Flyway

### Сервисы
- UserService — регистрация, вход, получение пользователя
- ChatService — отправка сообщений (MockLLM с 10 случайными ответами)
