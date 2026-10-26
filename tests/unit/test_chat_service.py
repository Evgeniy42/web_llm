from unittest.mock import Mock

from app.application_layer.contracts.llm_protocol import LLMProtocol
from app.application_layer.services.chat_service import ChatService


class TestChatService:
    def test_send_message_returns_llm_response(self):
        mock_llm = Mock(spec=LLMProtocol)
        mock_llm.generate_response.return_value = "Привет!"

        service = ChatService(llm=mock_llm)
        result = service.send_message("Hello")

        assert result == "Привет!"
        mock_llm.generate_response.assert_called_once_with("Hello")
