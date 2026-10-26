from dataclasses import dataclass

from app.application_layer.contracts.llm_protocol import LLMProtocol


@dataclass(slots=True)
class ChatService:
    llm: LLMProtocol

    def send_message(self, message: str) -> str:
        return self.llm.generate_response(message)
