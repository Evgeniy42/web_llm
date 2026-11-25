from collections.abc import Sequence
from typing import Protocol

from app.across_layers.entities.chunk_entity import ChunkEntity
from app.across_layers.entities.scored_chunk import ScoredChunk


class QdrantError(Exception):
    """Qdrant недоступен или отклонил операцию."""


class QdrantProtocol(Protocol):
    """Контракт векторного хранилища чанков (Qdrant).

    Хранилище хранит чанки документов вместе с векторами: один чанк —
    одна точка (point) коллекции. Идентификатор точки детерминирован
    (зависит только от doc_id и chunk_index), поэтому повторная запись
    того же чанка — это перезапись, а не дубликат (upsert).

    Методы рассчитаны на пакетную работу документа целиком (этап 4):
    документ нарезается на N чанков, векторизуется одним пакетным
    вызовом и записывается одним upsert'ом; при повторной загрузке
    того же doc_id «хвост» старых чанков (индексы за пределами нового
    числа чанков) удаляется, чтобы в коллекции не оставалось мёртвых
    данных прежней версии документа.

    Этап 5: search — векторный поиск ближайших чанков к запросу
    (top-k, опционально с фильтром по doc_id). Возвращает чанки
    с payload и score — сырьё для насыщения промпта (этап 7).
    """

    async def ensure_collection(self) -> None: ...

    async def upsert_chunks(self, chunks: Sequence[ChunkEntity], vectors: Sequence[Sequence[float]]) -> list[str]: ...

    async def count_chunks(self, doc_id: str) -> int: ...

    async def delete_chunks_from(self, doc_id: str, from_index: int) -> None: ...

    async def search(
        self,
        query_vector: Sequence[float],
        top_k: int,
        doc_id: str | None = None,
    ) -> list[ScoredChunk]: ...

    async def close(self) -> None: ...
