"""Юнит-тесты QdrantStore.search (этап 5): маппинг ответа Qdrant и фильтры.

HTTP-слой подменяется фейком AsyncQdrantClient: query_points записывает
аргументы и отдаёт точки с payload/score, как в реальном ответе.
"""

from types import SimpleNamespace

import pytest

from app.data_access_layer.clients.qdrant_store import QdrantStore


class FakeQdrantClient:
    def __init__(self, points=None, error: Exception | None = None) -> None:
        self._points = points or []
        self._error = error
        self.calls: list[dict] = []

    async def query_points(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(points=self._points)

    async def close(self) -> None:
        pass


def make_point(doc_id: str, index: int, score: float) -> SimpleNamespace:
    payload = {
        "doc_id": doc_id,
        "chunk_index": index,
        "source": f"{doc_id}.md",
        "content": f"содержимое {doc_id}:{index}",
    }
    return SimpleNamespace(payload=payload, score=score)


@pytest.fixture
def store_factory():
    def make(points=None, error=None) -> tuple[QdrantStore, FakeQdrantClient]:
        fake = FakeQdrantClient(points=points, error=error)
        store = QdrantStore.__new__(QdrantStore)
        store._collection = "rag_chunks"
        store._client = fake
        return store, fake

    return make


class TestSearch:
    async def test_points_mapped_to_scored_chunks(self, store_factory):
        store, fake = store_factory(
            points=[make_point("doc-a", 0, 0.95), make_point("doc-b", 3, 0.81)]
        )
        result = await store.search([0.1] * 1024, top_k=2)

        assert [s.score for s in result] == [0.95, 0.81]
        assert result[0].chunk.doc_id == "doc-a"
        assert result[0].chunk.chunk_index == 0
        assert result[0].chunk.source == "doc-a.md"
        assert result[0].chunk.content == "содержимое doc-a:0"
        assert result[1].chunk.doc_id == "doc-b"
        assert result[1].chunk.chunk_index == 3

        call = fake.calls[0]
        assert call["collection_name"] == "rag_chunks"
        assert call["limit"] == 2
        assert call["query"] == [0.1] * 1024
        assert call["with_payload"] is True

    async def test_no_doc_id_means_no_filter(self, store_factory):
        store, fake = store_factory(points=[])
        await store.search([0.0] * 4, top_k=5)

        assert fake.calls[0]["query_filter"] is None

    async def test_doc_id_builds_filter(self, store_factory):
        store, fake = store_factory(points=[])
        await store.search([0.0] * 4, top_k=5, doc_id="report")

        query_filter = fake.calls[0]["query_filter"]
        condition = query_filter.must[0]
        assert condition.key == "doc_id"
        assert condition.match.value == "report"

    async def test_empty_response_gives_empty_list(self, store_factory):
        store, _ = store_factory(points=[])
        assert await store.search([0.0] * 4, top_k=5) == []

    async def test_qdrant_error_wrapped(self, store_factory):
        from app.application_layer.contracts.client_contracts.qdrant_protocol import QdrantError

        store, _ = store_factory(error=ConnectionError("qdrant is down"))
        with pytest.raises(QdrantError, match="поиск"):
            await store.search([0.0] * 4, top_k=5)

    async def test_zero_top_k_rejected_before_request(self, store_factory):
        store, fake = store_factory(points=[])
        with pytest.raises(ValueError, match="top_k"):
            await store.search([0.0] * 4, top_k=0)
        assert fake.calls == []
