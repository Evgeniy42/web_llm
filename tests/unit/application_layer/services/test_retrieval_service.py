"""Юнит-тесты RetrievalService (этап 5): поиск чанков по текстовому запросу.

Фейки: embedding-клиент возвращает фиксированный вектор и запоминает
запрос, хранилище запоминает аргументы поиска и отдаёт готовый результат.
"""

from unittest.mock import Mock

import pytest

from app.across_layers.entities.chunk_entity import ChunkEntity
from app.across_layers.entities.scored_chunk import ScoredChunk
from app.application_layer.services.retrieval_service import RetrievalError, RetrievalService


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.embedded: list[str] = []

    async def embed_one(self, text: str) -> list[float]:
        self.embedded.append(text)
        return [1.0, 0.0, 0.0]


class FakeStore:
    def __init__(self, result: list[ScoredChunk]) -> None:
        self._result = result
        self.calls: list[tuple[list[float], int, str | None]] = []

    async def search(self, query_vector, top_k, doc_id=None) -> list[ScoredChunk]:
        self.calls.append((list(query_vector), top_k, doc_id))
        return self._result


def make_scored(score: float, doc_id: str = "doc", index: int = 0) -> ScoredChunk:
    chunk = ChunkEntity(doc_id=doc_id, chunk_index=index, source="doc.md", content=f"текст {doc_id}:{index}")
    return ScoredChunk(chunk=chunk, score=score)


@pytest.fixture
def client() -> FakeEmbeddingClient:
    return FakeEmbeddingClient()


@pytest.fixture
def store() -> FakeStore:
    return FakeStore([make_scored(0.9), make_scored(0.7, index=1)])


@pytest.fixture
def service(client, store) -> RetrievalService:
    return RetrievalService(client=client, store=store, default_top_k=5)


class TestSearch:
    async def test_query_embedded_and_passed_to_store(self, service, client, store):
        result = await service.search("как работает чанкинг")

        assert client.embedded == ["как работает чанкинг"]
        assert len(store.calls) == 1
        vector, top_k, doc_id = store.calls[0]
        assert vector == [1.0, 0.0, 0.0]
        assert top_k == 5  # дефолт из настроек
        assert doc_id is None
        assert [s.score for s in result] == [0.9, 0.7]

    async def test_explicit_top_k_overrides_default(self, service, store):
        await service.search("вопрос", top_k=10)

        assert store.calls[0][1] == 10

    async def test_doc_id_filter_passed_to_store(self, service, store):
        await service.search("вопрос", doc_id="report")

        assert store.calls[0][2] == "report"

    async def test_empty_result_is_allowed(self, client):
        service = RetrievalService(client=client, store=FakeStore([]), default_top_k=5)
        assert await service.search("вопрос") == []

    async def test_empty_query_rejected(self, service, store):
        with pytest.raises(ValueError, match="пустым"):
            await service.search("   ")
        assert store.calls == []

    async def test_zero_top_k_rejected(self, service):
        with pytest.raises(ValueError, match="top_k"):
            await service.search("вопрос", top_k=0)

    async def test_default_top_k_stored(self, client, store):
        service = RetrievalService(client=client, store=store, default_top_k=3)
        await service.search("вопрос")
        assert store.calls[0][1] == 3


class TestErrorWrapping:
    async def test_embedding_error_wrapped_into_retrieval_error(self):
        from app.application_layer.contracts.client_contracts.embedding_protocol import EmbeddingError

        client = FakeEmbeddingClient()
        client.embed_one = Mock(side_effect=EmbeddingError("llama-server недоступен"))
        service = RetrievalService(client=client, store=FakeStore([]), default_top_k=5)

        with pytest.raises(RetrievalError, match="Поиск контекста недоступен"):
            await service.search("вопрос")

    async def test_qdrant_error_wrapped_into_retrieval_error(self):
        from app.application_layer.contracts.client_contracts.qdrant_protocol import QdrantError

        store = FakeStore([])
        store.search = Mock(side_effect=QdrantError("qdrant отклонил запрос"))
        service = RetrievalService(client=FakeEmbeddingClient(), store=store, default_top_k=5)

        with pytest.raises(RetrievalError, match="Поиск контекста недоступен"):
            await service.search("вопрос")
