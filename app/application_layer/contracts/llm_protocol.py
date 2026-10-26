from typing import Protocol


class LLMProtocol(Protocol):
    def generate_response(self, message: str) -> str: ...
