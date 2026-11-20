import logging

import httpx

from app.application_layer.contracts.embedding_protocol import EmbeddingError

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """HTTP-клиент embedding-сервиса llama.cpp (Qwen3-Embedding).

    llama-server запущен с --embeddings и отдаёт OpenAI-совместимый
    POST /v1/embeddings: {"input": [...], "model": ...} ->
    {"data": [{"index": 0, "embedding": [...]}, ...]}. Пулинг на стороне
    сервиса (--pooling last), векторы уже L2-нормализованы, нормализовать
    повторно на клиенте не нужно.

    Клиент тонкий: без ретраев и кеширования — эмбеддинги чанков будут
    считаться пакетно на этапе записи в Qdrant, а в запросе поиска —
    одиночным вызовом.
    """

    def __init__(self, base_url: str, model: str, expected_dim: int, timeout: float = 60.0) -> None:
        self._model = model
        self._expected_dim = expected_dim
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Возвращает по вектору на каждый текст, в том же порядке.

        Args:
            texts: входные тексты. Пустой список не отправляется в сервис —
                возвращается пустой список (это удобно для чанкеров на этапе 2).

        Raises:
            EmbeddingError: сервис недоступен, вернул ошибку или размерность
                векторов не совпала с ожидаемой (контракт нарушен).
        """
        if not texts:
            return []

        try:
            response = await self._client.post(
                "/v1/embeddings",
                json={"input": texts, "model": self._model},
            )
        except httpx.HTTPError as e:
            raise EmbeddingError(f"Embedding-сервис недоступен: {e}") from e

        if response.status_code != 200:
            raise EmbeddingError(
                f"Embedding-сервис вернул HTTP {response.status_code}: {response.text[:500]}"
            )

        data = sorted(response.json()["data"], key=lambda item: item["index"])
        embeddings = [item["embedding"] for item in data]
        self._check_dims(embeddings, len(texts))
        return embeddings

    async def embed_one(self, text: str) -> list[float]:
        """Возвращает вектор одного текста."""
        return (await self.embed([text]))[0]

    async def close(self) -> None:
        """Закрывает HTTP-клиент и освобождает соединения."""
        await self._client.aclose()

    def _check_dims(self, embeddings: list[list[float]], expected_count: int) -> None:
        """Проверяет, что пришло нужное число векторов ожидаемой размерности.

        Проверка дешёвая (счёт элементов списков), а ловит класс ошибок
        «в compose подняли не ту модель / не тот alias» до того, как векторы
        уйдут в Qdrant на этапе 2.
        """
        if len(embeddings) != expected_count:
            raise EmbeddingError(
                f"Embedding-сервис вернул {len(embeddings)} векторов вместо {expected_count}"
            )
        for vector in embeddings:
            if len(vector) != self._expected_dim:
                raise EmbeddingError(
                    f"Размерность вектора {len(vector)} != ожидаемой {self._expected_dim}: "
                    "в embedding-сервисе другая модель"
                )
