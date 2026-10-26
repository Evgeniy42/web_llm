from typing import Final

from fastapi import status

from tests.resources.test_users import TEST_USER_1, TEST_USER_2

ID_KEY: Final = "id"
USERNAME_KEY: Final = "username"
EMAIL_KEY: Final = "email"
PASSWORD_KEY: Final = "password"
DETAIL_KEY: Final = "detail"

REGISTER_PATH: Final = "/user/register"
LOGIN_PATH: Final = "/user/login"


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
        duplicate = {**TEST_USER_2, EMAIL_KEY: TEST_USER_1[EMAIL_KEY]}

        response = client.post(REGISTER_PATH, json=duplicate)

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_register_duplicate_username_allowed(self, client):
        client.post(REGISTER_PATH, json=TEST_USER_1)
        duplicate = {**TEST_USER_2, USERNAME_KEY: TEST_USER_1[USERNAME_KEY]}

        response = client.post(REGISTER_PATH, json=duplicate)

        assert response.status_code == status.HTTP_201_CREATED

    def test_register_password_too_long(self, client):
        long_password = "я" * 40  # 80 байт в UTF-8, превышает лимит bcrypt 72 байт
        payload = {**TEST_USER_1, PASSWORD_KEY: long_password}

        response = client.post(REGISTER_PATH, json=payload)

        assert response.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    def test_register_invalid_email(self, client):
        payload = {**TEST_USER_1, EMAIL_KEY: "not-an-email"}

        response = client.post(REGISTER_PATH, json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLoginUser:
    def test_login_success(self, client):
        client.post(REGISTER_PATH, json=TEST_USER_1)

        response = client.post(LOGIN_PATH, json={
            EMAIL_KEY: TEST_USER_1[EMAIL_KEY],
            PASSWORD_KEY: TEST_USER_1[PASSWORD_KEY],
        })

        assert response.status_code == status.HTTP_200_OK
        assert response.json()[EMAIL_KEY] == TEST_USER_1[EMAIL_KEY]

    def test_login_wrong_password(self, client):
        client.post(REGISTER_PATH, json=TEST_USER_1)

        response = client.post(LOGIN_PATH, json={
            EMAIL_KEY: TEST_USER_1[EMAIL_KEY],
            PASSWORD_KEY: "wrongpassword",
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_user_not_found(self, client):
        response = client.post(LOGIN_PATH, json={
            EMAIL_KEY: "nonexistent@example.com",
            PASSWORD_KEY: "password123",
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetUserById:
    def test_get_user_by_id(self, client):
        register_response = client.post(REGISTER_PATH, json=TEST_USER_1)
        user_id = register_response.json()[ID_KEY]

        response = client.get(f"/user/{user_id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()[USERNAME_KEY] == TEST_USER_1[USERNAME_KEY]

    def test_get_user_not_found(self, client):
        response = client.get("/user/999999")

        assert response.status_code == status.HTTP_404_NOT_FOUND
