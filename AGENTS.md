# Веб-приложения для чата с LLM-моделью

### Краткое описание
Fullstack-приложение для чата с LLM. Backend: сервис пользователя (регистрация, вход,
получение по ID) и минимальный сценарий чата (10 случайных ответов вместо LLM).
Frontend: React-приложение для веб-интерфейса чата.

### Стек
- CI/CD: Docker Compose
- Backend: FastAPI, SQLAlchemy 2.x, Pydantic 2.x, PostgreSQL 16
- Frontend: React 19, Vite, oxlint
- Migration: Flyway (выполняется при старте приложения)
- Тесты: pytest (unit + integration с настоящей PostgreSQL)

### Архитектура backend
- `across_layers/entities` — внутренние сущности (UserEntity)
- `application_layer/` — бизнес-логика (сервисы, контракты, утилиты)
- `configuration/` — настройки, фабрика приложения, DatabaseManager
- `data_access_layer/` — ORM-модели, репозитории, мапперы
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
- UserService — регистрация, вход, получение пользователя
- ChatService — отправка сообщений (MockLLM с 10 случайными ответами)

### Скрипты frontend
- `npm run dev` — запуск dev-сервера Vite
- `npm run build` — сборка для продакшена
- `npm run lint` — проверка кода oxlint
- `npm run preview` — предпросмотр сборки
