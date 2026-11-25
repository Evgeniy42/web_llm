import logging
import uuid
from collections.abc import Sequence

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

from app.across_layers.entities.chunk_entity import ChunkEntity
from app.across_layers.entities.scored_chunk import ScoredChunk
from app.application_layer.contracts.client_contracts.qdrant_protocol import QdrantError

logger = logging.getLogger(__name__)

# Пространство имён для детерминированных UUID чанков: произвольная, но фиксированная
# константа проекта. Достаточно, чтобы id чанка зависел только от (doc_id, chunk_index)
# и не пересекался с UUID других систем.
_CHUNK_ID_NAMESPACE = uuid.UUID("6f1f5a24-7c9e-4c3a-b2d9-0e4a1c8f3b17")


class QdrantStore:
    """Асинхронный клиент Qdrant для хранения чанков документов.

    Коллекция создаётся при старте приложения (ensure_collection в lifespan):
    размерность вектора и метрика фиксированы моделью (1024, cosine).
    Запись — через upsert с детерминированным id: point_id =
    uuid5(doc_id + chunk_index), поэтому повторная загрузка того же чанка
    перезаписывает его, а не плодит дубликаты.

    Этап 4: запись стала пакетной (весь документ — одним upsert), плюс
    появились операции для обновления документов: посчитать старые чанки
    doc_id и удалить «хвост» (chunk_index >= нового числа чанков), чтобы
    повторная загрузка документа не оставляла в коллекции чанки прежней
    версии.
    """

    def __init__(self, url: str, collection: str, vector_size: int, timeout: float = 10.0) -> None:
        self._collection = collection
        self._vector_size = vector_size
        self._client = AsyncQdrantClient(url=url, timeout=timeout)

    async def ensure_collection(self) -> None:
        """Создаёт коллекцию, если её нет. Существующую коллекцию не трогает.

        Raises:
            QdrantError: Qdrant недоступен или отклонил создание.
        """
        try:
            exists = await self._client.collection_exists(self._collection)
            if not exists:
                await self._client.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(size=self._vector_size, distance=Distance.COSINE),
                )
                logger.info("Коллекция Qdrant '%s' создана (size=%d, cosine)", self._collection, self._vector_size)
        except Exception as e:
            raise QdrantError(f"Не удалось создать/проверить коллекцию '{self._collection}': {e}") from e

    async def upsert_chunks(self, chunks: Sequence[ChunkEntity], vectors: Sequence[Sequence[float]]) -> list[str]:
        """Пакетно записывает чанки документа с векторами (upsert).

        Args:
            chunks: чанки документа с метаданными (doc_id, chunk_index, source, content).
            vectors: векторы чанков в том же порядке (L2-нормализованы embedding-сервисом).
                Размер vectors обязан совпадать с размером chunks.

        Returns:
            Идентификаторы записанных точек в порядке chunks.

        Raises:
            QdrantError: Qdrant недоступен или отклонил запись.
        """
        if len(chunks) != len(vectors):
            raise ValueError(f"Число чанков ({len(chunks)}) != числу векторов ({len(vectors)})")

        points = [
            PointStruct(
                id=chunk_point_id(chunk.doc_id, chunk.chunk_index),
                vector=list(vector),
                payload={
                    "doc_id": chunk.doc_id,
                    "chunk_index": chunk.chunk_index,
                    "source": chunk.source,
                    "content": chunk.content,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        try:
            await self._client.upsert(collection_name=self._collection, points=points)
        except Exception as e:
            raise QdrantError(f"Qdrant отклонил пакетную запись {len(points)} чанков: {e}") from e
        return [str(point.id) for point in points]

    async def count_chunks(self, doc_id: str) -> int:
        """Возвращает число чанков документа в коллекции.

        Используется перед повторной загрузкой документа: если новая
        версия дала меньше чанков, старый «хвост» надо удалить.
        """
        try:
            result = await self._client.count(
                collection_name=self._collection,
                count_filter=self._doc_filter(doc_id),
            )
        except Exception as e:
            raise QdrantError(f"Qdrant отклонил подсчёт чанков '{doc_id}': {e}") from e
        count: int = result.count  # стабы qdrant-client отключены в mypy, count приходит как Any
        return count

    async def delete_chunks_from(self, doc_id: str, from_index: int) -> None:
        """Удаляет чанки документа с chunk_index >= from_index.

        Безусловно идемпотентно: если таких чанков нет, Qdrant просто
        удаляет ноль точек. Применяется после upsert новой версии
        документа, чтобы убрать чанки прежней версии, выходящие за
        пределы нового числа чанков.
        """
        selector = Filter(
            must=[
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                FieldCondition(key="chunk_index", range=Range(gte=from_index)),
            ]
        )
        try:
            await self._client.delete(collection_name=self._collection, points_selector=selector)
        except Exception as e:
            raise QdrantError(f"Qdrant отклонил удаление чанков '{doc_id}' с индекса {from_index}: {e}") from e

    async def search(
        self,
        query_vector: Sequence[float],
        top_k: int,
        doc_id: str | None = None,
    ) -> list[ScoredChunk]:
        """Ищет top_k чанков, ближайших к вектору запроса.

        Порядок результата — по убыванию близости (Qdrant так сортирует
        ответ). Без doc_id ищет по всей коллекции; с doc_id — только
        внутри одного документа (для сценариев «спросить по конкретному
        файлу»).

        Args:
            query_vector: L2-нормализованный вектор запроса (той же
                размерности, что и векторы коллекции).
            top_k: сколько ближайших чанков вернуть (>= 1).
            doc_id: опциональный фильтр по документу.

        Returns:
            Найденные чанки с payload и score (косинусная близость),
            отсортированные по убыванию релевантности.

        Raises:
            QdrantError: Qdrant недоступен или отклонил запрос.
        """
        if top_k < 1:
            raise ValueError(f"top_k должен быть >= 1, получен {top_k}")
        query_filter = self._doc_filter(doc_id) if doc_id is not None else None
        try:
            response = await self._client.query_points(
                collection_name=self._collection,
                query=list(query_vector),
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )
        except Exception as e:
            raise QdrantError(f"Qdrant отклонил поиск (top_k={top_k}): {e}") from e
        return [
            ScoredChunk(
                chunk=ChunkEntity(
                    doc_id=payload["doc_id"],
                    chunk_index=payload["chunk_index"],
                    source=payload["source"],
                    content=payload["content"],
                ),
                score=point.score,
            )
            for point in response.points
            if (payload := point.payload) is not None
        ]

    async def close(self) -> None:
        """Закрывает HTTP-соединения клиента."""
        await self._client.close()

    @staticmethod
    def _doc_filter(doc_id: str) -> Filter:
        return Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])


def chunk_point_id(doc_id: str, chunk_index: int) -> str:
    """Детерминированный UUID точки: один (doc_id, chunk_index) -> один id.

    Благодаря этому upsert идемпотентен: повторная отправка того же чанка
    перезаписывает существующую точку, а обновление документа (те же doc_id,
    другие chunk_index) заменяет старые чанки новыми без мусора.
    """
    return str(uuid.uuid5(_CHUNK_ID_NAMESPACE, f"{doc_id}:{chunk_index}"))
