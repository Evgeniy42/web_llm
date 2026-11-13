from urllib.parse import parse_qs

from fastapi import status

from tests.resources.api import (
    ACCESS_TOKEN_KEY,
    CODE_KEY,
    EMAIL_KEY,
    EXPIRES_IN_KEY,
    FRONTEND_AUTH_CALLBACK_URL,
    GOOGLE_CALLBACK_PATH,
    GOOGLE_LOGIN_PATH,
    GOOGLE_STATE_COOKIE,
    ID_KEY,
    LOGIN_PATH,
    LOGOUT_PATH,
    ME_PATH,
    PASSWORD_KEY,
    REFRESH_TOKEN_KEY,
    REGISTER_PATH,
    STATE_KEY,
    TOKEN_TYPE_KEY,
    USERNAME_KEY,
    bearer_headers,
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


class TestGoogleLogin:
    def test_login_google_redirects_to_keycloak_with_state_cookie(self, client):
        response = client.get(GOOGLE_LOGIN_PATH, follow_redirects=False)

        assert response.status_code == status.HTTP_302_FOUND
        location = response.headers["location"]
        assert STATE_KEY in location
        # kc_idp_hint: Keycloak сразу ведёт на форму входа Google
        assert "kc_idp_hint=google" in location
        # state против CSRF сохраняется в cookie и проверяется в callback'е
        assert client.cookies.get(GOOGLE_STATE_COOKIE)

    def _google_flow_state(self, client) -> str:
        """Первый шаг входа: получает state-cookie, как браузер после редиректа."""
        client.get(GOOGLE_LOGIN_PATH, follow_redirects=False)
        return client.cookies.get(GOOGLE_STATE_COOKIE)

    def _google_callback(self, client, code: str, state: str) -> dict:
        """Второй шаг входа: вызывает callback и возвращает параметры fragment'а редиректа.

        Callback больше не отдаёт JSON: браузер в навигации, поэтому и успех,
        и ошибка приходят редиректом 302 на фронтенд с параметрами после '#'.
        """
        response = client.get(
            GOOGLE_CALLBACK_PATH,
            params={CODE_KEY: code, STATE_KEY: state},
            follow_redirects=False,
        )

        assert response.status_code == status.HTTP_302_FOUND
        url, _, fragment = response.headers["location"].partition("#")
        assert url == FRONTEND_AUTH_CALLBACK_URL
        return parse_qs(fragment)

    def _me_id(self, client, access_token: str) -> int:
        """Профиль пользователя по выданному токену: callback не возвращает тело."""
        response = client.get(ME_PATH, headers=bearer_headers(access_token))
        assert response.status_code == status.HTTP_200_OK
        return response.json()[ID_KEY]

    def test_callback_rejects_state_mismatch(self, client, keycloak_mock):
        self._google_flow_state(client)

        params = self._google_callback(client, code="any-code", state="forged-state")

        assert params["error"][0]
        # State одноразовый: cookie сброшен и при ошибке
        assert not client.cookies.get(GOOGLE_STATE_COOKIE)

    def test_callback_rejects_unknown_code(self, client, keycloak_mock):
        state = self._google_flow_state(client)

        params = self._google_callback(client, code="unknown-code", state=state)

        assert params["error"][0]
        assert not client.cookies.get(GOOGLE_STATE_COOKIE)

    def test_callback_creates_profile_for_new_google_user(self, client, keycloak_mock):
        # Пользователь вошёл через Google впервые: брокер создал его в Keycloak
        code = keycloak_mock.add_google_user(TEST_USER_1[EMAIL_KEY])
        state = self._google_flow_state(client)

        params = self._google_callback(client, code=code, state=state)

        assert "error" not in params
        assert params[ACCESS_TOKEN_KEY][0]
        assert params[REFRESH_TOKEN_KEY][0]
        assert params[TOKEN_TYPE_KEY] == ["Bearer"]
        assert int(params[EXPIRES_IN_KEY][0]) > 0
        # State одноразовый: cookie сброшен после успешного входа
        assert not client.cookies.get(GOOGLE_STATE_COOKIE)

        # Профиль созданного пользователя: имя выводится из email, пароля нет
        response = client.get(ME_PATH, headers=bearer_headers(params[ACCESS_TOKEN_KEY][0]))
        assert response.json()[EMAIL_KEY] == TEST_USER_1[EMAIL_KEY]
        assert response.json()[USERNAME_KEY] == TEST_USER_1[EMAIL_KEY].split("@")[0]

    def test_callback_uses_google_name_as_username(self, client, keycloak_mock):
        # Имя из профиля Google имеет приоритет над локальной частью email
        code = keycloak_mock.add_google_user(TEST_USER_1[EMAIL_KEY], full_name="Ivan Petrov")
        state = self._google_flow_state(client)

        response = client.get(
            GOOGLE_CALLBACK_PATH,
            params={CODE_KEY: code, STATE_KEY: state},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()[USERNAME_KEY] == "Ivan Petrov"

    def test_callback_logs_into_existing_account(self, client, keycloak_mock):
        # Пользователь регистрировался по паролю, теперь вошёл через Google:
        # email совпадает — вход в тот же аккаунт, дубликат не создаётся
        register_response = client.post(REGISTER_PATH, json=TEST_USER_1)
        user_id = register_response.json()[ID_KEY]
        code = keycloak_mock.add_google_user(TEST_USER_1[EMAIL_KEY])
        state = self._google_flow_state(client)

        params = self._google_callback(client, code=code, state=state)

        assert self._me_id(client, params[ACCESS_TOKEN_KEY][0]) == user_id

    def test_callback_second_login_assigns_no_duplicate(self, client, keycloak_mock):
        # Повторный вход через Google: роль user назначена при первом входе,
        # локальный профиль уже есть — вход проходит без побочных эффектов
        code = keycloak_mock.add_google_user(TEST_USER_1[EMAIL_KEY])
        state = self._google_flow_state(client)
        first = self._google_callback(client, code=code, state=state)

        code = keycloak_mock.add_google_user(TEST_USER_1[EMAIL_KEY])
        state = self._google_flow_state(client)
        second = self._google_callback(client, code=code, state=state)

        first_id = self._me_id(client, first[ACCESS_TOKEN_KEY][0])
        assert self._me_id(client, second[ACCESS_TOKEN_KEY][0]) == first_id


class TestGetMe:
    def test_get_me_returns_profile_of_current_user(self, client):
        register_response = client.post(REGISTER_PATH, json=TEST_USER_1)
        access_token = register_response.json()[ACCESS_TOKEN_KEY]

        response = client.get(ME_PATH, headers=bearer_headers(access_token))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data[ID_KEY] == register_response.json()[ID_KEY]
        assert data[USERNAME_KEY] == TEST_USER_1[USERNAME_KEY]
        assert data[EMAIL_KEY] == TEST_USER_1[EMAIL_KEY]
        assert PASSWORD_KEY not in data

    def test_get_me_without_token(self, client):
        response = client.get(ME_PATH)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
