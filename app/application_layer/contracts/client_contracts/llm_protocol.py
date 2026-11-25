from typing import Protocol


class LLMError(Exception):
    """LLM-сервис недоступен, отклонил запрос или вернул некорректный ответ."""


class LLMProtocol(Protocol):
    """Контракт генеративной модели (чат).

    За контрактом — OpenAI-совместимый API через AItunnel (`~z-ai/glm-latest`).
    Этап 7: вопрос пользователя идёт как user-сообщение, а собранный
    RAG-контекст (найденные чанки) — как системный промпт; без system
    вызов остаётся «сырым» чатом (режим заглушки, используется в тестах).
    """

    async def generate_response(self, message: str, system: str | None = None) -> str: ...

    async def close(self) -> None: ...
