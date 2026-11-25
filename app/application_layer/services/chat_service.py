from dataclasses import dataclass

from app.application_layer.contracts.client_contracts.llm_protocol import LLMProtocol
from app.application_layer.prompts.rag_prompt import build_system_prompt
from app.application_layer.services.retrieval_service import RetrievalService


@dataclass(slots=True)
class ChatService:
    """Сценарий диалога: поиск контекста -> сборка промпта -> ответ LLM.

    Этап 7: сообщение пользователя проходит полный RAG-пайплайн —
    RetrievalService ищет релевантные чанки в Qdrant, шаблон промпта
    (application_layer.prompts.rag_prompt) собирает из них системный
    промпт, LLM отвечает с опорой на контекст. Порог отсечения по score
    пока не применяется: все найденные top_k чанки попадают в промпт,
    модель сама опирается на релевантное.
    """

    llm: LLMProtocol
    retrieval: RetrievalService

    async def send_message(self, message: str) -> str:
        """Отвечает на сообщение пользователя, опираясь на загруженные документы.

        Args:
            message: текст сообщения пользователя.

        Returns:
            Сгенерированный текст ответа.

        Raises:
            RetrievalError: поиск контекста недоступен (эмбеддинги/Qdrant).
            LLMError: LLM-сервис недоступен или вернул некорректный ответ.
        """
        chunks = await self.retrieval.search(message)
        system = build_system_prompt(chunks)
        return await self.llm.generate_response(message, system=system)
