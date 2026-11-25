"""Внутренний микросервис конвертации документов (docling).

Принимает файл любого поддерживаемого формата, сам определяет формат
по содержимому и отдаёт Markdown + метаданные. Работает только во
внутренней docker-сети: app ходит сюда по имени сервиса, снаружи
порт не опубликован.

Слои (намеренно без DI-фреймворков и сторонних библиотек):
- controllers/ — тонкий HTTP-слой (UploadFile, коды ответов);
- service/ — вся работа с docling; единый экземпляр DoclingService
  через ленивый синглтон get_conversion_service().

Веса моделей docling кешируются в смонтированный volume
(DOCLING_ARTIFACTS_PATH), чтобы не скачивать их при каждом
пересоздании контейнера.
"""

import logging

from fastapi import FastAPI

from controllers import convert_router, health_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="docling-service", docs_url=None, redoc_url=None, openapi_url=None)

app.include_router(health_router)
app.include_router(convert_router)
