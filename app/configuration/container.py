from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.application_layer.contracts.keycloak_protocol import KeycloakClientProtocol
from app.application_layer.services.chat_service import ChatService
from app.application_layer.services.user_service import UserService
from app.configuration.database import DatabaseManager
from app.data_access_layer.repositories.mock_llm import MockLLM
from app.data_access_layer.repositories.user_repository import UserRepository


class AppProvider(Provider):
    scope = Scope.REQUEST

    # Settings, DatabaseManager и KeycloakClientProtocol поставляются в контейнер
    # через context из app.configuration.application_factory.create_app

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
    ) -> UserService:
        return UserService(repository=repository, keycloak=keycloak)

    @provide
    def mock_llm(self) -> MockLLM:
        return MockLLM()

    @provide
    def chat_service(self, llm: MockLLM) -> ChatService:
        return ChatService(llm=llm)
