from fastapi import status


class TestChatAPI:
    def test_send_message_success(self, client):
        response = client.post("/chat/send", json={"message": "Привет!"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0

    def test_send_message_empty(self, client):
        response = client.post("/chat/send", json={"message": ""})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
