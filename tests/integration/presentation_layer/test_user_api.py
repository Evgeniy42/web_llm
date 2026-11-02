from fastapi import status

from tests.resources.api import (
    EMAIL_KEY,
    ID_KEY,
    LOGIN_PATH,
    PASSWORD_KEY,
    REGISTER_PATH,
    USERNAME_KEY,
    user_by_id_path,
)
from tests.resources.users import (
    INVALID_EMAIL,
    LONG_PASSWORD,
    NONEXISTENT_USER_EMAIL,
    NONEXISTENT_USER_ID,
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

    def test_register_password_too_long(self, client):
        payload = register_payload(TEST_USER_1, password=LONG_PASSWORD)

        response = client.post(REGISTER_PATH, json=payload)

        assert response.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    def test_register_invalid_email(self, client):
        payload = register_payload(TEST_USER_1, email=INVALID_EMAIL)

        response = client.post(REGISTER_PATH, json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLoginUser:
    def test_login_success(self, client):
        client.post(REGISTER_PATH, json=TEST_USER_1)

        response = client.post(LOGIN_PATH, json=login_payload(TEST_USER_1))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()[EMAIL_KEY] == TEST_USER_1[EMAIL_KEY]

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
