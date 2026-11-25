from typing import Protocol

from app.across_layers.entities.converted_document import ConvertedDocument


class DoclingError(Exception):
    """Микросервис конвертации недоступен или не смог обработать файл."""


class DoclingClientProtocol(Protocol):
    """Контракт клиента внутреннего микросервиса конвертации документов.

    Сервис работает только во внутренней docker-сети (docling-service:8082)
    и делает одно: файл любого поддерживаемого формата -> Markdown.
    """

    async def convert(self, filename: str, content: bytes) -> ConvertedDocument: ...

    async def close(self) -> None: ...
