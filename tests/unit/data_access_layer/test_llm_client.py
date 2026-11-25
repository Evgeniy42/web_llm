"""Юнит-тесты AItunnelLLM (этап 6): OpenAI-совместимый клиент чата.

HTTP-слой подменяется фейком AsyncOpenAI: проверяем, что клиент шлёт
сырое сообщение пользователя одним user-сообщением (заглушка промпта),
правильно мапит ошибки API и падает без ключа.
"""

from types import SimpleNamespace
from typing import ClassVar

import httpx
import pytest
from openai import APIStatusError

import app.data_access_layer.clients.llm_client as llm_module
from app.application_layer.contracts.client_contracts.llm_protocol import LLMError
from app.data_access_layer.clients.llm_client import AItunnelLLM


class FakeCompletions:
    """Подмена openai-ресурса chat.completions."""

    def __init__(self, response=None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


class FakeAsyncOpenAI:
    """Записывает конструкторные аргументы и проксирует chat.completions."""

    instances: ClassVar[list["FakeAsyncOpenAI"]] = []

    def __init__(self, api_key: str, base_url: str, timeout: float) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.completions = FakeCompletions()
        self.closed = False
        FakeAsyncOpenAI.instances.append(self)

    @property
    def chat(self):
        return SimpleNamespace(completions=self.completions)

    async def close(self) -> None:
        self.closed = True


def make_completion(content: str | None):
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


@pytest.fixture(autouse=True)
def patch_openai(monkeypatch):
    FakeAsyncOpenAI.instances.clear()
    monkeypatch.setattr(llm_module, "AsyncOpenAI", FakeAsyncOpenAI)
    return FakeAsyncOpenAI


class TestAItunnelLLM:
    async def test_sends_raw_user_message_without_system(self, patch_openai):
        client = AItunnelLLM(api_key="token", base_url="https://api.aitunnel.ru/v1/", model="~z-ai/glm-latest")
        fake = patch_openai.instances[-1]
        fake.completions._response = make_completion("Ответ модели")

        result = await client.generate_response("Привет, как дела?")

        assert result == "Ответ модели"
        (call,) = fake.completions.calls
        assert call["model"] == "~z-ai/glm-latest"
        # Без system: исходное сообщение уходит одним user-сообщением
        assert call["messages"] == [{"role": "user", "content": "Привет, как дела?"}]

    async def test_system_prompt_prepended_before_user_message(self, patch_openai):
        client = AItunnelLLM(api_key="token", base_url="https://x/", model="m")
        fake = patch_openai.instances[-1]
        fake.completions._response = make_completion("Ответ с контекстом")

        await client.generate_response("Что такое Qdrant?", system="Ты ассистент. Контекст: ...")

        (call,) = fake.completions.calls
        assert call["messages"] == [
            {"role": "system", "content": "Ты ассистент. Контекст: ..."},
            {"role": "user", "content": "Что такое Qdrant?"},
        ]

    def test_client_configured_from_constructor(self, patch_openai):
        AItunnelLLM(api_key="token", base_url="https://api.aitunnel.ru/v1/", model="m", timeout=30.0)

        (fake,) = patch_openai.instances
        assert fake.api_key == "token"
        assert fake.base_url == "https://api.aitunnel.ru/v1/"
        assert fake.timeout == 30.0

    def test_empty_api_key_rejected(self, patch_openai):
        with pytest.raises(LLMError, match="LLM_API_KEY"):
            AItunnelLLM(api_key="", base_url="https://api.aitunnel.ru/v1/", model="m")

    async def test_empty_choices_becomes_llm_error(self, patch_openai):
        client = AItunnelLLM(api_key="token", base_url="https://x/", model="m")
        fake = patch_openai.instances[-1]
        fake.completions._response = SimpleNamespace(choices=[])

        with pytest.raises(LLMError, match="пустой ответ"):
            await client.generate_response("текст")

    async def test_api_status_error_becomes_llm_error(self, patch_openai):
        request = httpx.Request("POST", "https://api.aitunnel.ru/v1/chat/completions")
        response = httpx.Response(401, request=request)
        api_error = APIStatusError("invalid token", response=response, body=None)

        client = AItunnelLLM(api_key="bad-token", base_url="https://x/", model="m")
        fake = patch_openai.instances[-1]
        fake.completions._error = api_error

        with pytest.raises(LLMError, match="401"):
            await client.generate_response("текст")

    async def test_close_closes_underlying_client(self, patch_openai):
        client = AItunnelLLM(api_key="token", base_url="https://x/", model="m")
        fake = patch_openai.instances[-1]

        await client.close()

        assert fake.closed is True
