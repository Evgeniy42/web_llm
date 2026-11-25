import logging

from app.across_layers.entities.scored_chunk import ScoredChunk
from app.application_layer.contracts.client_contracts.embedding_protocol import EmbeddingClientProtocol, EmbeddingError
from app.application_layer.contracts.client_contracts.qdrant_protocol import QdrantError, QdrantProtocol

logger = logging.getLogger(__name__)


class RetrievalError(Exception):
    """Поиск контекста недоступен: упал эмбеддинг-сервис или Qdrant."""


class RetrievalService:
    """Сценарий поиска релевантных чанков для насыщения контекста (этап 5).

    Сквозной путь запроса: текст вопроса -> один эмбеддинг запроса
    (embed_one, тот же сервис и та же модель, что векторизуют чанки, —
    поэтому запрос и чанки лежат в одном векторном пространстве) ->
    векторный поиск top-k в Qdrant (опционально с фильтром по doc_id).

    Сервис не знает про LLM и промпт: он возвращает найденные чанки
    с оценками, а сборка системного промпта из них — этап 7.
    """

    def __init__(
        self,
        client: EmbeddingClientProtocol,
        store: QdrantProtocol,
        default_top_k: int,
    ) -> None:
        self._client = client
        self._store = store
        self._default_top_k = default_top_k

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        doc_id: str | None = None,
    ) -> list[ScoredChunk]:
        """Ищет чанки, релевантные текстовому запросу.

        Args:
            query: текстовый вопрос пользователя.
            top_k: сколько чанков вернуть; None — настройка по умолчанию
                (Settings.rag_search_top_k).
            doc_id: искать только внутри одного документа; None — по всей
                коллекции.

        Returns:
            Найденные чанки с оценкой близости, отсортированные по
            убыванию релевантности. Может быть пустым списком, если
            коллекция пуста.

        Raises:
            ValueError: пустой запрос или top_k < 1.
            RetrievalError: эмбеддинг-сервис или Qdrant недоступны
                (причина сохранена в цепочке исключений и логе).
        """
        if not query.strip():
            raise ValueError("Поисковый запрос не должен быть пустым")
        k = top_k if top_k is not None else self._default_top_k
        if k < 1:
            raise ValueError(f"top_k должен быть >= 1, получен {k}")

        try:
            vector = await self._client.embed_one(query)
            found = await self._store.search(vector, k, doc_id)
        except (EmbeddingError, QdrantError) as e:
            # Единая ошибка сценария для HTTP-слоя: клиент чата не должен
            # различать, какой именно внешний сервис упал. rag_error_handler
            # остаётся контрактом эндпоинта загрузки документа.
            raise RetrievalError(f"Поиск контекста недоступен: {e}") from e
        logger.info(
            "Поиск чанков: query=%r top_k=%d doc_id=%s -> найдено %d чанков (лучший score=%.4f)",
            query[:80],
            k,
            doc_id,
            len(found),
            found[0].score if found else float("nan"),
        )
        return found
