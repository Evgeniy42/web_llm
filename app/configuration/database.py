from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class DatabaseManager:
    """Управляет пулом соединений и фабрикой асинхронных сессий."""

    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url)
        self.session_factory = async_sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

    async def dispose(self):
        await self.engine.dispose()

    def get_session(self) -> AsyncSession:
        return self.session_factory()
