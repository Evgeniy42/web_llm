import logging

from openai import APIConnectionError, APIError, APIStatusError, AsyncOpenAI, AuthenticationError

from app.application_layer.contracts.client_contracts.llm_protocol import LLMError, LLMProtocol

logger = logging.getLogger(__name__)


class AItunnelLLM(LLMProtocol):
    """Клиент генеративной модели через OpenAI-совместимый API AItunnel.

    base_url по умолчанию https://api.aitunnel.ru/v1/, модель по умолчанию
    ~z-ai/glm-latest (настраиваются через Settings). Клиент тонкий: один
    вызов chat.completions на запрос, без ретраев — повторная отправка
    сообщения пользователя и есть ретрай со стороны UI.

    Этап 7: messages = [system?, user] — RAG-контекст (собранный из найденных
    чанков системный промпт, см. application_layer.prompts.rag_prompt) идёт
    первым сообщением, вопрос пользователя — вторым.
    """

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float = 60.0) -> None:
        if not api_key:
            raise LLMError("LLM_API_KEY не задан: впишите токен AItunnel в .env")
        self._model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    async def generate_response(self, message: str, system: str | None = None) -> str:
        """Возвращает ответ модели на сообщение пользователя.

        Args:
            message: вопрос пользователя (user-сообщение).
            system: опциональный системный промпт с RAG-контекстом;
                None — «сырой» чат без контекста (режим заглушки).

        Raises:
            LLMError: туннель недоступен, токен отклонён, превышен лимит
                или ответ пришёл без текста.
        """
        messages = [{"role": "system", "content": system}] if system is not None else []
        messages.append({"role": "user", "content": message})
        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
        except AuthenticationError as e:
            raise LLMError(f"AItunnel отклонил токен: {e}") from e
        except APIStatusError as e:
            raise LLMError(f"AItunnel вернул HTTP {e.status_code}: {e.message}") from e
        except APIConnectionError as e:
            raise LLMError(f"AItunnel недоступен: {e}") from e
        except APIError as e:
            raise LLMError(f"Ошибка OpenAI-совместимого API: {e}") from e

        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            raise LLMError("Модель вернула пустой ответ")
        return content

    async def close(self) -> None:
        """Закрывает HTTP-соединения клиента."""
        await self._client.close()
