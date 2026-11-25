from typing import Protocol

from app.application_layer.contracts.service_contracts.tokenizer_protocol import TokenizerProtocol


class EmbeddingError(Exception):
    """Embedding-сервис недоступен или вернул ошибку."""


class EmbeddingClientProtocol(TokenizerProtocol, Protocol):
    """Контракт клиента эмбеддингов (llama.cpp server, Qwen3-Embedding).

    Клиент ходит в OpenAI-совместимый эндпоинт /v1/embeddings и возвращает
    по L2-нормализованному вектору на каждый входной текст. Сервис
    разворачивается в docker-compose (сервис `embeddings`) и не хранит
    состояния, поэтому контракт предельно узкий.

    Через TokenizerProtocol клиент дополнительно даёт настоящий токенайзер
    модели (/tokenize, /detokenize): чанкинг на этапе 4 считает токены
    в том же пространстве, в котором эмбеддинг-модель читает текст.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_one(self, text: str) -> list[float]: ...

    async def close(self) -> None: ...
