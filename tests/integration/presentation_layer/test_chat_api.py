from fastapi import status

from tests.resources.api import (
    ACCESS_TOKEN_COOKIE,
    CODE_KEY,
    EMAIL_KEY,
    LOGIN_CALLBACK_PATH,
    LOGIN_PATH,
    MESSAGE_KEY,
    NO_SUBSCRIPTION_MESSAGE,
    OAUTH_STATE_COOKIE,
    RESPONSE_KEY,
    SEND_MESSAGE_PATH,
    STATE_KEY,
    SUBSCRIPTION_PATH,
    USERNAME_KEY,
    bearer_headers,
)
from tests.resources.users import TEST_USER_1


def _login(client, keycloak_mock) -> str:
    """Логинит тестового пользователя через mock Keycloak и возвращает access-токен.

    Полный флоу authorization code + PKCE: пользователь создан в моке
    (страница Keycloak), backend обменивает код на токены в callback'е,
    сессия устанавливается в cookie — токен читаем оттуда.
    """
    code = keycloak_mock.add_user_with_code(
        TEST_USER_1[EMAIL_KEY], full_name=TEST_USER_1[USERNAME_KEY]
    )
    client.get(LOGIN_PATH, follow_redirects=False)
    state = client.cookies.get(OAUTH_STATE_COOKIE)
    response = client.get(
        LOGIN_CALLBACK_PATH,
        params={CODE_KEY: code, STATE_KEY: state},
        follow_redirects=False,
    )
    assert response.status_code == status.HTTP_302_FOUND
    return client.cookies.get(ACCESS_TOKEN_COOKIE)


def _subscribe(client, keycloak_mock, access_token: str) -> str:
    """Оформляет подписку и возвращает новый access-токен с ролью vip_user.

    Роль попадает в JWT снимком при входе, поэтому после назначения vip_user
    нужен повторный логин — как с настоящим Keycloak.
    """
    response = client.post(SUBSCRIPTION_PATH, headers=bearer_headers(access_token))
    assert response.status_code == status.HTTP_200_OK
    assert MESSAGE_KEY in response.json()

    return _login(client, keycloak_mock)


class TestChatAPI:
    def test_send_message_success_for_vip_user(self, client, keycloak_mock):
        access_token = _subscribe(client, keycloak_mock, _login(client, keycloak_mock))

        response = client.post(
            SEND_MESSAGE_PATH, json={"message": "Привет!"}, headers=bearer_headers(access_token)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert RESPONSE_KEY in data
        assert len(data[RESPONSE_KEY]) > 0

    def test_send_message_denied_for_user_without_subscription(self, client, keycloak_mock):
        access_token = _login(client, keycloak_mock)

        response = client.post(
            SEND_MESSAGE_PATH, json={"message": "Привет!"}, headers=bearer_headers(access_token)
        )

        # Отказ приходит как обычное сообщение чата, чтобы фронтенд показал его в диалоге
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[RESPONSE_KEY] == NO_SUBSCRIPTION_MESSAGE

    def test_send_message_unauthorized_without_session(self, client):
        response = client.post(SEND_MESSAGE_PATH, json={"message": "Привет!"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_send_message_unauthorized_with_invalid_token(self, client):
        response = client.post(
            SEND_MESSAGE_PATH,
            json={"message": "Привет!"},
            headers=bearer_headers("not-a-token"),
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_send_message_empty(self, client, keycloak_mock):
        access_token = _subscribe(client, keycloak_mock, _login(client, keycloak_mock))

        response = client.post(
            SEND_MESSAGE_PATH, json={"message": ""}, headers=bearer_headers(access_token)
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestSubscriptionAPI:
    def test_subscribe_success(self, client, keycloak_mock):
        access_token = _login(client, keycloak_mock)

        response = client.post(SUBSCRIPTION_PATH, headers=bearer_headers(access_token))

        assert response.status_code == status.HTTP_200_OK
        assert MESSAGE_KEY in response.json()

    def test_subscribe_grants_chat_access_only_after_relogin(self, client, keycloak_mock):
        access_token = _login(client, keycloak_mock)
        client.post(SUBSCRIPTION_PATH, headers=bearer_headers(access_token))

        # Роль зашита в выданный токен снимком: старый токен по-прежнему без подписки
        old_token_response = client.post(
            SEND_MESSAGE_PATH, json={"message": "Привет!"}, headers=bearer_headers(access_token)
        )
        assert old_token_response.json()[RESPONSE_KEY] == NO_SUBSCRIPTION_MESSAGE

        # После повторного входа токен содержит vip_user, чат доступен
        new_token = _login(client, keycloak_mock)
        new_token_response = client.post(
            SEND_MESSAGE_PATH, json={"message": "Привет!"}, headers=bearer_headers(new_token)
        )
        assert new_token_response.status_code == status.HTTP_200_OK

    def test_subscribe_unauthorized_without_session(self, client):
        response = client.post(SUBSCRIPTION_PATH)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
