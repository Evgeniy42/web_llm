from fastapi import status

from tests.resources.api import (
    ACCESS_TOKEN_KEY,
    LOGIN_PATH,
    MESSAGE_KEY,
    NO_SUBSCRIPTION_MESSAGE,
    REGISTER_PATH,
    RESPONSE_KEY,
    SEND_MESSAGE_PATH,
    SUBSCRIPTION_PATH,
    bearer_headers,
)
from tests.resources.users import TEST_USER_1, login_payload


def _register_and_login(client) -> str:
    """Регистрирует тестового пользователя и возвращает access-токен после повторного входа."""
    client.post(REGISTER_PATH, json=TEST_USER_1)
    login_response = client.post(LOGIN_PATH, json=login_payload(TEST_USER_1))
    return login_response.json()[ACCESS_TOKEN_KEY]


def _subscribe(client, access_token: str) -> str:
    """Оформляет подписку и возвращает новый access-токен с ролью vip_user.

    Роль попадает в JWT снимком при входе, поэтому после назначения vip_user
    нужен повторный логин — как с настоящим Keycloak.
    """
    response = client.post(SUBSCRIPTION_PATH, headers=bearer_headers(access_token))
    assert response.status_code == status.HTTP_200_OK
    assert MESSAGE_KEY in response.json()

    login_response = client.post(LOGIN_PATH, json=login_payload(TEST_USER_1))
    return login_response.json()[ACCESS_TOKEN_KEY]


class TestChatAPI:
    def test_send_message_success_for_vip_user(self, client):
        access_token = _subscribe(client, _register_and_login(client))

        response = client.post(
            SEND_MESSAGE_PATH, json={"message": "Привет!"}, headers=bearer_headers(access_token)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert RESPONSE_KEY in data
        assert len(data[RESPONSE_KEY]) > 0

    def test_send_message_denied_for_user_without_subscription(self, client):
        access_token = _register_and_login(client)

        response = client.post(
            SEND_MESSAGE_PATH, json={"message": "Привет!"}, headers=bearer_headers(access_token)
        )

        # Отказ приходит как обычное сообщение чата, чтобы фронтенд показал его в диалоге
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[RESPONSE_KEY] == NO_SUBSCRIPTION_MESSAGE

    def test_send_message_unauthorized_without_token(self, client):
        response = client.post(SEND_MESSAGE_PATH, json={"message": "Привет!"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_send_message_unauthorized_with_invalid_token(self, client):
        response = client.post(
            SEND_MESSAGE_PATH,
            json={"message": "Привет!"},
            headers=bearer_headers("not-a-token"),
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_send_message_empty(self, client):
        access_token = _subscribe(client, _register_and_login(client))

        response = client.post(
            SEND_MESSAGE_PATH, json={"message": ""}, headers=bearer_headers(access_token)
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestSubscriptionAPI:
    def test_subscribe_success(self, client):
        access_token = _register_and_login(client)

        response = client.post(SUBSCRIPTION_PATH, headers=bearer_headers(access_token))

        assert response.status_code == status.HTTP_200_OK
        assert MESSAGE_KEY in response.json()

    def test_subscribe_grants_chat_access_only_after_relogin(self, client):
        access_token = _register_and_login(client)
        client.post(SUBSCRIPTION_PATH, headers=bearer_headers(access_token))

        # Роль зашита в выданный токен снимком: старый токен по-прежнему без подписки
        old_token_response = client.post(
            SEND_MESSAGE_PATH, json={"message": "Привет!"}, headers=bearer_headers(access_token)
        )
        assert old_token_response.json()[RESPONSE_KEY] == NO_SUBSCRIPTION_MESSAGE

        # После повторного входа токен содержит vip_user, чат доступен
        new_token = client.post(LOGIN_PATH, json=login_payload(TEST_USER_1)).json()[ACCESS_TOKEN_KEY]
        new_token_response = client.post(
            SEND_MESSAGE_PATH, json={"message": "Привет!"}, headers=bearer_headers(new_token)
        )
        assert new_token_response.status_code == status.HTTP_200_OK

    def test_subscribe_unauthorized_without_token(self, client):
        response = client.post(SUBSCRIPTION_PATH)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
