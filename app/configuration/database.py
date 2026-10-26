from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class DatabaseManager:
    """Управляет пулом соединений и фабрикой сессий."""

    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

    def dispose(self):
        self.engine.dispose()

    def get_session(self):
        return self.session_factory()
