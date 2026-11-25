from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.application_layer.contracts.client_contracts.docling_protocol import DoclingClientProtocol
from app.application_layer.contracts.client_contracts.embedding_protocol import EmbeddingClientProtocol
from app.application_layer.contracts.client_contracts.keycloak_protocol import KeycloakClientProtocol
from app.application_layer.contracts.client_contracts.llm_protocol import LLMProtocol
from app.application_layer.contracts.client_contracts.qdrant_protocol import QdrantProtocol
from app.application_layer.services.chat_service import ChatService
from app.application_layer.services.embedding_service import EmbeddingService
from app.application_layer.services.markdown_chunker import MarkdownChunker
from app.application_layer.services.retrieval_service import RetrievalService
from app.application_layer.services.user_service import UserService
from app.configuration.database import DatabaseManager
from app.configuration.settings import Settings
from app.data_access_layer.clients.llm_client import AItunnelLLM
from app.data_access_layer.repositories.user_repository import UserRepository


class AppProvider(Provider):
    scope = Scope.REQUEST

    # Settings, DatabaseManager и KeycloakClientProtocol поставляются в контейнер
    # через context из app.configuration.application_factory.create_app

    @provide
    def markdown_chunker(self, settings: Settings) -> MarkdownChunker:
        return MarkdownChunker(
            min_tokens=settings.rag_chunk_min_tokens,
            max_tokens=settings.rag_chunk_max_tokens,
            overlap_ratio=settings.rag_chunk_overlap_ratio,
        )

    @provide
    def embedding_service(
        self,
        chunker: MarkdownChunker,
        docling: DoclingClientProtocol,
        client: EmbeddingClientProtocol,
        store: QdrantProtocol,
    ) -> EmbeddingService:
        return EmbeddingService(chunker, docling, client, store)

    @provide
    def retrieval_service(
        self,
        client: EmbeddingClientProtocol,
        store: QdrantProtocol,
        settings: Settings,
    ) -> RetrievalService:
        return RetrievalService(
            client=client,
            store=store,
            default_top_k=settings.rag_search_top_k,
        )

    @provide
    async def db_session(self, db_manager: DatabaseManager) -> AsyncIterator[AsyncSession]:
        async with db_manager.get_session() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            else:
                await session.commit()

    @provide
    def user_repository(self, session: AsyncSession) -> UserRepository:
        return UserRepository(session)

    @provide
    def user_service(
        self,
        repository: UserRepository,
        keycloak: KeycloakClientProtocol,
        settings: Settings,
    ) -> UserService:
        return UserService(
            repository=repository,
            keycloak=keycloak,
            redirect_uri=settings.keycloak_redirect_uri,
            google_idp_alias=settings.google_idp_alias,
        )

    @provide
    def llm_client(self, settings: Settings) -> LLMProtocol:
        return AItunnelLLM(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )

    @provide
    def chat_service(self, llm: LLMProtocol, retrieval: RetrievalService) -> ChatService:
        return ChatService(llm=llm, retrieval=retrieval)
