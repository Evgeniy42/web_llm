from fastapi import status

from tests.resources.api import (
    ACCESS_TOKEN_KEY,
    EMAIL_KEY,
    EXPIRES_IN_KEY,
    ID_KEY,
    LOGIN_PATH,
    LOGOUT_PATH,
    PASSWORD_KEY,
    REFRESH_TOKEN_KEY,
    REGISTER_PATH,
    TOKEN_TYPE_KEY,
    USERNAME_KEY,
    user_by_id_path,
)
from tests.resources.users import (
    INVALID_EMAIL,
    NONEXISTENT_USER_EMAIL,
    NONEXISTENT_USER_ID,
    SHORT_PASSWORD,
    TEST_USER_1,
    TEST_USER_2,
    WRONG_PASSWORD,
    login_payload,
    register_payload,
)


class TestRegisterUser:
    def test_register_user_success(self, client):
        response = client.post(REGISTER_PATH, json=TEST_USER_1)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data[USERNAME_KEY] == TEST_USER_1[USERNAME_KEY]
        assert data[EMAIL_KEY] == TEST_USER_1[EMAIL_KEY]
        assert PASSWORD_KEY not in data
        # Автоматическая авторизация: регистрация сразу возвращает JWT сессии
        assert data[ACCESS_TOKEN_KEY]
        assert data[TOKEN_TYPE_KEY] == "Bearer"
        assert data[EXPIRES_IN_KEY] > 0

    def test_register_duplicate_email(self, client):
        client.post(REGISTER_PATH, json=TEST_USER_1)
        duplicate = register_payload(TEST_USER_2, email=TEST_USER_1[EMAIL_KEY])

        response = client.post(REGISTER_PATH, json=duplicate)

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_register_duplicate_username_allowed(self, client):
        client.post(REGISTER_PATH, json=TEST_USER_1)
        duplicate = register_payload(TEST_USER_2, username=TEST_USER_1[USERNAME_KEY])

        response = client.post(REGISTER_PATH, json=duplicate)

        assert response.status_code == status.HTTP_201_CREATED

    def test_register_password_too_short(self, client):
        payload = register_payload(TEST_USER_1, password=SHORT_PASSWORD)

        response = client.post(REGISTER_PATH, json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_invalid_email(self, client):
        payload = register_payload(TEST_USER_1, email=INVALID_EMAIL)

        response = client.post(REGISTER_PATH, json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLoginUser:
    def test_login_success_returns_jwt(self, client):
        client.post(REGISTER_PATH, json=TEST_USER_1)

        response = client.post(LOGIN_PATH, json=login_payload(TEST_USER_1))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data[EMAIL_KEY] == TEST_USER_1[EMAIL_KEY]
        # Сессия: backend вернул JWT, выпущенный Keycloak
        assert data[ACCESS_TOKEN_KEY]
        assert data[TOKEN_TYPE_KEY] == "Bearer"
        assert data[EXPIRES_IN_KEY] > 0

    def test_login_wrong_password(self, client):
        client.post(REGISTER_PATH, json=TEST_USER_1)

        response = client.post(LOGIN_PATH, json=login_payload(TEST_USER_1, WRONG_PASSWORD))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_user_not_found(self, client):
        response = client.post(
            LOGIN_PATH,
            json=login_payload({EMAIL_KEY: NONEXISTENT_USER_EMAIL}, TEST_USER_1[PASSWORD_KEY]),
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestLogoutUser:
    def test_logout_success(self, client):
        register_response = client.post(REGISTER_PATH, json=TEST_USER_1)
        refresh_token = register_response.json()[REFRESH_TOKEN_KEY]

        response = client.post(LOGOUT_PATH, json={REFRESH_TOKEN_KEY: refresh_token})

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_logout_twice_is_idempotent(self, client):
        # Настоящий Keycloak отвечает 204 на повторный logout с уже отозванным токеном
        register_response = client.post(REGISTER_PATH, json=TEST_USER_1)
        refresh_token = register_response.json()[REFRESH_TOKEN_KEY]
        client.post(LOGOUT_PATH, json={REFRESH_TOKEN_KEY: refresh_token})

        response = client.post(LOGOUT_PATH, json={REFRESH_TOKEN_KEY: refresh_token})

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_logout_invalid_token(self, client):
        response = client.post(LOGOUT_PATH, json={REFRESH_TOKEN_KEY: "not-a-token"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_without_token(self, client):
        response = client.post(LOGOUT_PATH, json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetUserById:
    def test_get_user_by_id(self, client):
        register_response = client.post(REGISTER_PATH, json=TEST_USER_1)
        user_id = register_response.json()[ID_KEY]

        response = client.get(user_by_id_path(user_id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()[USERNAME_KEY] == TEST_USER_1[USERNAME_KEY]

    def test_get_user_not_found(self, client):
        response = client.get(user_by_id_path(NONEXISTENT_USER_ID))

        assert response.status_code == status.HTTP_404_NOT_FOUND
