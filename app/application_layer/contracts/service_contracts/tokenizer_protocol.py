from typing import Protocol


class TokenizeError(Exception):
    """Токенайзер недоступен или вернул ошибку."""


class TokenizerProtocol(Protocol):
    """Контракт токенайзера текста (id-токены модели).

    Реализуется embedding-клиентом llama.cpp server: эндпоинты /tokenize
    и /detokenize используют тот же токенайзер, что и эмбеддинг-модель,
    поэтому счёт токенов для чанкинга совпадает с тем, как модель
    «видит» текст. Чанкер принимает этот контракт и не зависит
    от конкретной реализации — в тестах подставляется детерминированный
    фейк.
    """

    async def tokenize(self, text: str) -> list[int]: ...

    async def detokenize(self, tokens: list[int]) -> str: ...
