from unittest.mock import Mock

from app.application_layer.contracts.llm_protocol import LLMProtocol
from app.application_layer.services.chat_service import ChatService
from tests.resources.mocks import LLM_RESPONSE, USER_MESSAGE


class TestChatService:
    async def test_send_message_returns_llm_response(self):
        mock_llm = Mock(spec=LLMProtocol)
        mock_llm.generate_response.return_value = LLM_RESPONSE

        service = ChatService(llm=mock_llm)
        result = await service.send_message(USER_MESSAGE)

        assert result == LLM_RESPONSE
        mock_llm.generate_response.assert_called_once_with(USER_MESSAGE)
