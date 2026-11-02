from fastapi import status

from tests.resources.api import RESPONSE_KEY, SEND_MESSAGE_PATH


class TestChatAPI:
    def test_send_message_success(self, client):
        response = client.post(SEND_MESSAGE_PATH, json={"message": "Привет!"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert RESPONSE_KEY in data
        assert len(data[RESPONSE_KEY]) > 0

    def test_send_message_empty(self, client):
        response = client.post(SEND_MESSAGE_PATH, json={"message": ""})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
