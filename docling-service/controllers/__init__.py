"""HTTP-слой docling-service: роутеры эндпоинтов.

Контроллеры тонкие: читают HTTP-вход (UploadFile), зовут сервисный
слой и маппят его доменные ошибки в коды ответов. Бизнес-логики
(работа с docling, файлами, моделями) здесь нет.
"""

from controllers.convert import router as convert_router
from controllers.health import router as health_router

__all__ = ["convert_router", "health_router"]
