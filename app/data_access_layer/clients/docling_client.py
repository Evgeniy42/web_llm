import httpx

from app.across_layers.entities.converted_document import ConvertedDocument
from app.application_layer.contracts.client_contracts.docling_protocol import DoclingError


class DoclingClient:
    """HTTP-клиент внутреннего микросервиса docling-service (POST /convert).

    Файл пересылается multipart/form-data; сервис сам определяет формат
    по расширению и содержимому. Микросервис доступен только внутри
    docker-сети, порт наружу не публикуется.
    """

    def __init__(self, base_url: str, timeout: float = 300.0) -> None:
        # Таймаут большой: конвертация скана на десятках страниц — десятки секунд
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def convert(self, filename: str, content: bytes) -> ConvertedDocument:
        """Конвертирует файл в Markdown через микросервис.

        Raises:
            DoclingError: сервис недоступен или вернул ошибку (битый файл,
                неподдерживаемый формат — в этом случае сервис отвечает 422,
                детали в сообщении).
        """
        try:
            response = await self._client.post(
                "/convert",
                files={"file": (filename, content)},
            )
        except httpx.HTTPError as e:
            raise DoclingError(f"Сервис конвертации недоступен: {e}") from e

        if response.status_code != 200:
            try:
                detail = response.json().get("detail", response.text[:300])
            except ValueError:
                detail = response.text[:300]
            raise DoclingError(f"Сервис конвертации вернул HTTP {response.status_code}: {detail}")

        payload = response.json()
        return ConvertedDocument(
            filename=payload["filename"],
            format=payload["format"],
            markdown=payload["markdown"],
        )

    async def close(self) -> None:
        """Закрывает HTTP-соединения."""
        await self._client.aclose()
