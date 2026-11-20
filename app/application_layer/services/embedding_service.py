from app.application_layer.contracts.embedding_protocol import EmbeddingClientProtocol


class EmbeddingService:
    """Сценарии приложения поверх эмбеддингов.

    Этап 1: единственный сценарий — проверка доступности и корректности
    embedding-сервиса. На этапе 2 сюда добавится метод, вычисляющий векторы
    чанков перед записью в Qdrant.
    """

    def __init__(self, client: EmbeddingClientProtocol) -> None:
        self._client = client

    async def embed(self, text: str) -> list[float]:
        """Возвращает L2-нормализованный вектор текста."""
        return await self._client.embed_one(text)
