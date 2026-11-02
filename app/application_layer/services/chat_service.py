from dataclasses import dataclass

from app.application_layer.contracts.llm_protocol import LLMProtocol


@dataclass(slots=True)
class ChatService:
    llm: LLMProtocol

    async def send_message(self, message: str) -> str:
        """Передаёт сообщение пользователя в LLM и возвращает ответ.

        Args:
            message: текст сообщения пользователя.

        Returns:
            Сгенерированный текст ответа.
        """
        return self.llm.generate_response(message)
