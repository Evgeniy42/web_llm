import logging
import uuid
from pathlib import Path

from app.across_layers.entities.chunk_entity import ChunkEntity
from app.application_layer.contracts.client_contracts.docling_protocol import DoclingClientProtocol, DoclingError
from app.application_layer.contracts.client_contracts.embedding_protocol import EmbeddingClientProtocol
from app.application_layer.contracts.client_contracts.qdrant_protocol import QdrantProtocol
from app.application_layer.services.markdown_chunker import MarkdownChunker

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Сценарии приложения: конвертация документов, эмбеддинги, запись чанков.

    Этап 4: документ проходит четыре шага — конвертация в Markdown
    микросервисом docling-service, нарезка на чанки по структуре
    Markdown (MarkdownChunker, счёт токенов — настоящим токенайзером
    модели), пакетная векторизация чанков одним вызовом /v1/embeddings
    и пакетная запись в Qdrant. Повторная загрузка того же doc_id
    перезаписывает чанки и удаляет «хвост» прежней версии.
    """

    def __init__(
        self,
        chunker: MarkdownChunker,
        docling: DoclingClientProtocol,
        client: EmbeddingClientProtocol,
        store: QdrantProtocol,
    ) -> None:
        self._chunker = chunker
        self._docling = docling
        self._client = client
        self._store = store

    async def embed(self, text: str) -> list[float]:
        """Возвращает L2-нормализованный вектор текста."""
        return await self._client.embed_one(text)

    async def ingest_document(
        self,
        filename: str,
        content: bytes,
        doc_id: str | None = None,
    ) -> tuple[str, int, str]:
        """Загружает документ в векторное хранилище (конвертация + чанкинг + запись).

        Args:
            filename: имя файла с расширением (определяет формат конвертации).
            content: сырые байты файла.
            doc_id: идентификатор документа; если не задан, берётся имя
                файла без расширения. Повторная загрузка с тем же doc_id
                заменяет документ: совпавшие chunk_index перезаписываются
                upsert'ом, чанки старой версии за пределами нового числа
                чанков удаляются.

        Returns:
            Тройка (doc_id, chunks_count, format): идентификатор документа,
            число записанных чанков и определённый docling формат.

        Raises:
            DoclingError: документ не содержит извлекаемого текста.
        """
        doc_id = doc_id or Path(filename).stem
        converted = await self._docling.convert(filename, content)
        if not converted.markdown.strip():
            raise DoclingError(f"Документ '{filename}' не содержит извлекаемого текста")

        texts = await self._chunker.split(converted.markdown, self._client)
        vectors = await self._client.embed(texts)

        old_count = await self._store.count_chunks(doc_id)
        chunks = [
            ChunkEntity(doc_id=doc_id, chunk_index=index, source=filename, content=text)
            for index, text in enumerate(texts)
        ]
        await self._store.upsert_chunks(chunks, vectors)

        if old_count > len(chunks):
            await self._store.delete_chunks_from(doc_id, len(chunks))
            logger.info(
                "Документ '%s': удалено %d чанков(а) прежней версии (хвост с индекса %d)",
                doc_id,
                old_count - len(chunks),
                len(chunks),
            )
        return doc_id, len(chunks), converted.format

    async def embed_and_store(
        self,
        text: str,
        doc_id: str | None = None,
        chunk_index: int = 0,
        source: str = "manual",
    ) -> str:
        """Векторизует текст и записывает его в Qdrant как один чанк.

        Ручной путь записи одиночного чанка (тестовый эндпоинт этапа 1).
        Повторная запись с тем же doc_id и chunk_index перезаписывает
        чанк (идемпотентность).

        Returns:
            Идентификатор записанной точки в Qdrant.
        """
        doc_id = doc_id or str(uuid.uuid4())
        chunk = ChunkEntity(
            doc_id=doc_id,
            chunk_index=chunk_index,
            source=source,
            content=text,
        )
        vector = await self._client.embed_one(text)
        point_ids = await self._store.upsert_chunks([chunk], [vector])
        return point_ids[0]
