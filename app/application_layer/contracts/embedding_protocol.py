from typing import Protocol


class EmbeddingError(Exception):
    """Embedding-сервис недоступен или вернул ошибку."""


class EmbeddingClientProtocol(Protocol):
    """Контракт клиента эмбеддингов (llama.cpp server, Qwen3-Embedding).

    Клиент ходит в OpenAI-совместимый эндпоинт /v1/embeddings и возвращает
    по L2-нормализованному вектору на каждый входной текст. Сервис
    разворачивается в docker-compose (сервис `embeddings`) и не хранит
    состояния, поэтому контракт предельно узкий.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_one(self, text: str) -> list[float]: ...

    async def close(self) -> None: ...
