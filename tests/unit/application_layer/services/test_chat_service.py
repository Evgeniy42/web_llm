"""Юнит-тесты ChatService (этап 7): полный RAG-пайплайн сообщения.

Пайплайн send_message: RetrievalService ищет чанки -> шаблон промпта
собирает системный промпт -> LLM получает (сообщение, system).
Фейки: retrieval отдаёт заданные чанки, LLM — записывает вызов.
"""

from unittest.mock import Mock

import pytest

from app.across_layers.entities.chunk_entity import ChunkEntity
from app.across_layers.entities.scored_chunk import ScoredChunk
from app.application_layer.contracts.client_contracts.llm_protocol import LLMProtocol
from app.application_layer.prompts.rag_prompt import NO_CONTEXT_PLACEHOLDER, build_context, build_system_prompt
from app.application_layer.services.chat_service import ChatService
from app.application_layer.services.retrieval_service import RetrievalError, RetrievalService
from tests.resources.mocks import LLM_RESPONSE, USER_MESSAGE


def make_chunk(content: str, source: str = "doc.md", index: int = 0) -> ScoredChunk:
    return ScoredChunk(
        chunk=ChunkEntity(doc_id="doc", chunk_index=index, source=source, content=content),
        score=0.9,
    )


def make_service(chunks: list[ScoredChunk]) -> tuple[ChatService, Mock, Mock]:
    mock_retrieval = Mock(spec=RetrievalService)
    mock_retrieval.search.return_value = chunks
    mock_llm = Mock(spec=LLMProtocol)
    mock_llm.generate_response.return_value = LLM_RESPONSE
    return ChatService(llm=mock_llm, retrieval=mock_retrieval), mock_llm, mock_retrieval


class TestChatService:
    async def test_message_searches_context_and_passes_system_prompt(self):
        chunks = [make_chunk("Qdrant хранит эмбеддинги чанков.", index=0)]
        service, mock_llm, mock_retrieval = make_service(chunks)

        result = await service.send_message(USER_MESSAGE)

        assert result == LLM_RESPONSE
        mock_retrieval.search.assert_called_once_with(USER_MESSAGE)
        mock_llm.generate_response.assert_called_once()
        kwargs = mock_llm.generate_response.call_args.kwargs
        assert kwargs["system"] is not None
        assert "Qdrant хранит эмбеддинги чанков." in kwargs["system"]
        assert "doc.md" in kwargs["system"]
        # сообщение пользователя передаётся позиционно
        assert mock_llm.generate_response.call_args.args == (USER_MESSAGE,)

    async def test_empty_search_builds_no_context_prompt(self):
        service, mock_llm, _ = make_service([])

        await service.send_message(USER_MESSAGE)

        system = mock_llm.generate_response.call_args.kwargs["system"]
        assert NO_CONTEXT_PLACEHOLDER in system

    async def test_retrieval_error_propagates_without_llm_call(self):
        service, mock_llm, mock_retrieval = make_service([])
        mock_retrieval.search.side_effect = RetrievalError("Qdrant недоступен")

        with pytest.raises(RetrievalError):
            await service.send_message(USER_MESSAGE)
        mock_llm.generate_response.assert_not_called()


class TestRagPromptTemplate:
    def test_build_context_numbers_chunks_with_sources(self):
        chunks = [
            make_chunk("первый текст", source="a.md", index=0),
            make_chunk("второй текст", source="b.md", index=1),
        ]
        context = build_context(chunks)

        assert "[1] Источник: a.md" in context
        assert "[2] Источник: b.md" in context
        assert "первый текст" in context and "второй текст" in context

    def test_empty_chunks_give_placeholder(self):
        assert NO_CONTEXT_PLACEHOLDER in build_system_prompt([])
