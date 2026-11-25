"""Юнит-тесты EmbeddingService (этап 4): пакетная запись документа и удаление хвоста.

Внешние клиенты заменены фейками: docling возвращает готовый Markdown,
embedding-клиент считает токены словами (тот же FakeTokenizer-принцип,
что в тестах чанкера), хранилище записывает вызовы в память.
"""

import pytest

from app.across_layers.entities.converted_document import ConvertedDocument
from app.application_layer.contracts.client_contracts.docling_protocol import DoclingError
from app.application_layer.services.embedding_service import EmbeddingService
from app.application_layer.services.markdown_chunker import MarkdownChunker
from tests.unit.application_layer.services.test_markdown_chunker import FakeTokenizer


def make_sentence(tag: str) -> str:
    return " ".join(f"слово{tag}{i}" for i in range(31)) + "."


def make_markdown(paragraphs: int) -> str:
    # предложения различаются тегом, чтобы чанки с overlap не совпадали побайтово
    return "\n\n".join(make_sentence(p) for p in range(paragraphs))


class FakeDoclingClient:
    def __init__(self, markdown: str, detected_format: str = "markdown") -> None:
        self._document = ConvertedDocument(filename="doc.md", format=detected_format, markdown=markdown)
        self.requests: list[tuple[str, bytes]] = []

    async def convert(self, filename: str, content: bytes) -> ConvertedDocument:
        self.requests.append((filename, content))
        return self._document

    async def close(self) -> None:
        pass


class FakeEmbeddingClient(FakeTokenizer):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.5] * 4 for _ in texts]

    async def embed_one(self, text: str) -> list[float]:
        return [0.5] * 4

    async def close(self) -> None:
        pass


class FakeStore:
    """Запоминает вызовы; old_count имитирует чанки прежней версии документа."""

    def __init__(self, old_count: int = 0) -> None:
        self.old_count = old_count
        self.upserted: list | None = None
        self.deleted: tuple[str, int] | None = None

    async def count_chunks(self, doc_id: str) -> int:
        return self.old_count

    async def upsert_chunks(self, chunks, vectors) -> list[str]:
        assert len(chunks) == len(vectors)
        self.upserted = list(chunks)
        return [f"point-{c.chunk_index}" for c in chunks]

    async def delete_chunks_from(self, doc_id: str, from_index: int) -> None:
        self.deleted = (doc_id, from_index)

    async def close(self) -> None:
        pass


@pytest.fixture
def chunker() -> MarkdownChunker:
    # маленькие пределы: 1 предложение (31 токен) = 1 чанк, N предложений = N чанков
    return MarkdownChunker(min_tokens=20, max_tokens=60, overlap_ratio=0.1)


class TestIngestDocument:
    async def test_document_split_into_chunks_and_stored(self, chunker):
        docling = FakeDoclingClient(markdown=make_markdown(3), detected_format="pdf")
        client = FakeEmbeddingClient()
        store = FakeStore(old_count=0)
        service = EmbeddingService(chunker, docling, client, store)

        doc_id, chunks_count, fmt = await service.ingest_document("report.pdf", b"%PDF-fake")

        assert doc_id == "report"
        assert chunks_count == 3
        assert fmt == "pdf"
        assert store.deleted is None  # старых чанков не было — удалять нечего
        assert [c.chunk_index for c in store.upserted] == [0, 1, 2]
        assert all(c.doc_id == "report" for c in store.upserted)
        assert all(c.source == "report.pdf" for c in store.upserted)
        assert len({c.content for c in store.upserted}) == 3

    async def test_doc_id_defaults_to_filename_stem(self, chunker):
        service = EmbeddingService(
            chunker, FakeDoclingClient(markdown=make_markdown(1)), FakeEmbeddingClient(), FakeStore()
        )
        doc_id, _, _ = await service.ingest_document("notes.txt", b"text")
        assert doc_id == "notes"

    async def test_explicit_doc_id_wins(self, chunker):
        service = EmbeddingService(
            chunker, FakeDoclingClient(markdown=make_markdown(1)), FakeEmbeddingClient(), FakeStore()
        )
        doc_id, _, _ = await service.ingest_document("notes.txt", b"text", doc_id="custom-id")
        assert doc_id == "custom-id"

    async def test_reupload_deletes_stale_tail(self, chunker):
        # Прежняя версия документа дала 5 чанков, новая — 3: хвост [3..4] удаляется
        store = FakeStore(old_count=5)
        service = EmbeddingService(chunker, FakeDoclingClient(markdown=make_markdown(3)), FakeEmbeddingClient(), store)

        _, chunks_count, _ = await service.ingest_document("report.pdf", b"%PDF-fake")

        assert chunks_count == 3
        assert store.deleted == ("report", 3)

    async def test_reupload_with_more_chunks_keeps_everything(self, chunker):
        store = FakeStore(old_count=2)
        service = EmbeddingService(chunker, FakeDoclingClient(markdown=make_markdown(4)), FakeEmbeddingClient(), store)

        _, chunks_count, _ = await service.ingest_document("report.pdf", b"%PDF-fake")

        assert chunks_count == 4
        assert store.deleted is None

    async def test_empty_markdown_rejected(self, chunker):
        service = EmbeddingService(
            chunker, FakeDoclingClient(markdown="   \n "), FakeEmbeddingClient(), FakeStore()
        )
        with pytest.raises(DoclingError, match="не содержит"):
            await service.ingest_document("blank.txt", b"")
