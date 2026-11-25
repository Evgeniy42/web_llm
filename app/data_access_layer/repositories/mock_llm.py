import random
from typing import ClassVar

from app.application_layer.contracts.client_contracts.llm_protocol import LLMProtocol


class MockLLM(LLMProtocol):
    """Заглушка LLM: возвращает один из 10 случайных ответов.

    Снята с продакшен-сборки при переходе на AItunnel (этап 6);
    живёт дальше как контрактно-совместимый фейк для тестов.
    Явное наследование LLMProtocol — заодно статическая проверка
    соответствия контракту (mypy).
    """

    RESPONSES: ClassVar[list[str]] = [
        "Интересный вопрос! Давайте разберёмся.",
        "Я понимаю, о чём вы говорите.",
        "Это хорошая тема для обсуждения.",
        "Могу предложить несколько вариантов.",
        "Давайте посмотрим на это с другой стороны.",
        "Отличный вопрос!",
        "Я бы посоветовал обратить внимание на детали.",
        "Это зависит от контекста.",
        "Попробуем разобрать по шагам.",
        "Спасибо за ваше сообщение!",
    ]

    async def generate_response(self, message: str, system: str | None = None) -> str:
        return random.choice(self.RESPONSES)

    async def close(self) -> None:
        pass
