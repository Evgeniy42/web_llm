from urllib.parse import parse_qs, urlparse

from fastapi import status

from tests.resources.api import (
    ACCESS_TOKEN_COOKIE,
    CODE_KEY,
    EMAIL_KEY,
    ERROR_KEY,
    FRONTEND_AUTH_CALLBACK_URL,
    GOOGLE_LOGIN_PATH,
    ID_KEY,
    LOGIN_CALLBACK_PATH,
    LOGIN_PATH,
    LOGOUT_PATH,
    ME_PATH,
    OAUTH_PKCE_VERIFIER_COOKIE,
    OAUTH_STATE_COOKIE,
    REFRESH_TOKEN_COOKIE,
    ROLES_KEY,
    STATE_KEY,
    USERNAME_KEY,
    bearer_headers,
)
from tests.resources.users import TEST_USER_1


def _start_login(client, path: str = LOGIN_PATH) -> str:
    """Первый шаг входа: получает state-cookie, как браузер после редиректа."""
    response = client.get(path, follow_redirects=False)
    assert response.status_code == status.HTTP_302_FOUND
    state = client.cookies.get(OAUTH_STATE_COOKIE)
    assert state
    return state


def _callback(client, code: str, state: str):
    """Второй шаг входа: вызывает единый callback с кодом и state."""
    return client.get(
        LOGIN_CALLBACK_PATH,
        params={CODE_KEY: code, STATE_KEY: state},
        follow_redirects=False,
    )


def _login(client, keycloak_mock, email: str = TEST_USER_1[EMAIL_KEY], full_name: str | None = None):
    """Полный вход через mock Keycloak: пользователь создан, вход завершён на его странице.

    Возвращает ответ callback'а (302). Сессионные cookie уже в cookie-jar клиента.
    """
    code = keycloak_mock.add_user_with_code(email, full_name=full_name)
    state = _start_login(client)
    response = _callback(client, code, state)
    assert response.status_code == status.HTTP_302_FOUND
    return response


def _callback_error(response) -> str:
    """Извлекает сообщение об ошибке из fragment'а редиректа на фронтенд."""
    assert response.status_code == status.HTTP_302_FOUND
    url = response.headers["location"]
    base, _, fragment = url.partition("#")
    assert base == FRONTEND_AUTH_CALLBACK_URL
    return parse_qs(fragment)[ERROR_KEY][0]


class TestLoginRedirect:
    def test_login_redirects_to_keycloak_with_pkce_and_state_cookies(self, client):
        response = client.get(LOGIN_PATH, follow_redirects=False)

        assert response.status_code == status.HTTP_302_FOUND
        location = response.headers["location"]
        assert STATE_KEY in location
        # PKCE: challenge в запросе авторизации, verifier — в HttpOnly-cookie backend'а
        assert "code_challenge=" in location
        assert "code_challenge_method=S256" in location
        # Обычный вход — без подсказки identity provider'а
        assert "kc_idp_hint" not in location
        assert client.cookies.get(OAUTH_STATE_COOKIE)
        assert client.cookies.get(OAUTH_PKCE_VERIFIER_COOKIE)

    def test_login_google_redirects_with_idp_hint(self, client):
        response = client.get(GOOGLE_LOGIN_PATH, follow_redirects=False)

        assert response.status_code == status.HTTP_302_FOUND
        # kc_idp_hint: Keycloak сразу ведёт на форму входа Google
        assert "kc_idp_hint=google" in response.headers["location"]
        assert client.cookies.get(OAUTH_STATE_COOKIE)
        assert client.cookies.get(OAUTH_PKCE_VERIFIER_COOKIE)


class TestLoginCallback:
    def test_callback_success_sets_session_cookies_and_redirects(self, client, keycloak_mock):
        response = _login(client, keycloak_mock)

        # Успех: редирект на фронтенд БЕЗ параметров и токенов в URL
        location = response.headers["location"]
        assert location == FRONTEND_AUTH_CALLBACK_URL
        assert "#" not in location
        # Сессия — в HttpOnly-cookie
        assert client.cookies.get(ACCESS_TOKEN_COOKIE)
        assert client.cookies.get(REFRESH_TOKEN_COOKIE)
        # Cookie попытки входа одноразовые: сброшены после успешного входа
        assert not client.cookies.get(OAUTH_STATE_COOKIE)
        assert not client.cookies.get(OAUTH_PKCE_VERIFIER_COOKIE)

    def test_callback_rejects_state_mismatch(self, client, keycloak_mock):
        _start_login(client)

        response = _callback(client, code="any-code", state="forged-state")

        assert _callback_error(response)
        # Сессия не создана
        assert not client.cookies.get(ACCESS_TOKEN_COOKIE)
        # State одноразовый: cookie сброшен и при ошибке
        assert not client.cookies.get(OAUTH_STATE_COOKIE)

    def test_callback_rejects_unknown_code(self, client, keycloak_mock):
        state = _start_login(client)

        response = _callback(client, code="unknown-code", state=state)

        assert _callback_error(response)
        assert not client.cookies.get(ACCESS_TOKEN_COOKIE)

    def test_callback_rejects_missing_pkce_verifier(self, client, keycloak_mock):
        # Верifier-cookie нет (потеряна/подменена попытка входа): state совпадает,
        # но обмен кода невозможен — вход отклоняется
        code = keycloak_mock.add_user_with_code(TEST_USER_1[EMAIL_KEY])
        client.cookies.set(OAUTH_STATE_COOKIE, "known-state")

        response = _callback(client, code=code, state="known-state")

        assert _callback_error(response)
        assert not client.cookies.get(ACCESS_TOKEN_COOKIE)

    def test_callback_creates_profile_for_new_user(self, client, keycloak_mock):
        # Пользователь вошёл впервые: Keycloak создал его мимо backend'а
        _login(client, keycloak_mock)

        # Профиль создан: доступен по сессионной cookie, без Bearer-заголовка
        response = client.get(ME_PATH)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data[EMAIL_KEY] == TEST_USER_1[EMAIL_KEY]
        # Имени из соцсети нет — имя выводится из локальной части email
        assert data[USERNAME_KEY] == TEST_USER_1[EMAIL_KEY].split("@")[0]
        # Роли приходят из токена: фронтенд не декодирует JWT сам
        assert "user" in data[ROLES_KEY]

    def test_callback_uses_google_name_as_username(self, client, keycloak_mock):
        # Имя из профиля Google имеет приоритет над локальной частью email
        _login(client, keycloak_mock, full_name="Ivan Petrov")

        response = client.get(ME_PATH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()[USERNAME_KEY] == "Ivan Petrov"

    def test_callback_logs_into_existing_account(self, client, keycloak_mock):
        # Повторный вход тем же способом: мок возвращает sub того же пользователя
        # (в настоящем Keycloak связывание аккаунтов завершено самим Keycloak)
        _login(client, keycloak_mock)
        first_id = client.get(ME_PATH).json()[ID_KEY]

        _login(client, keycloak_mock)
        second_id = client.get(ME_PATH).json()[ID_KEY]

        assert second_id == first_id

    def test_callback_assigns_default_role_when_missing(self, client, keycloak_mock):
        # Пользователь без базовой роли (краевой случай): backend доназначает её
        # при первом входе, в токен она попадает со следующего входа
        keycloak_mock.register_user(TEST_USER_1[EMAIL_KEY], with_default_role=False)
        code = keycloak_mock.issue_auth_code(TEST_USER_1[EMAIL_KEY])
        state = _start_login(client)
        _callback(client, code, state)
        assert "user" not in client.get(ME_PATH).json()[ROLES_KEY]

        _login(client, keycloak_mock)

        assert "user" in client.get(ME_PATH).json()[ROLES_KEY]


class TestLogout:
    def test_logout_revokes_session_and_clears_cookies(self, client, keycloak_mock):
        _login(client, keycloak_mock)
        assert client.cookies.get(ACCESS_TOKEN_COOKIE)

        response = client.post(LOGOUT_PATH)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not client.cookies.get(ACCESS_TOKEN_COOKIE)
        assert not client.cookies.get(REFRESH_TOKEN_COOKIE)
        # Сессия завершена: /me недоступен
        assert client.get(ME_PATH).status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_without_session_is_noop(self, client):
        response = client.post(LOGOUT_PATH)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_logout_twice_is_idempotent(self, client, keycloak_mock):
        _login(client, keycloak_mock)

        assert client.post(LOGOUT_PATH).status_code == status.HTTP_204_NO_CONTENT
        assert client.post(LOGOUT_PATH).status_code == status.HTTP_204_NO_CONTENT


class TestGetMe:
    def test_get_me_with_bearer_header_is_supported(self, client, keycloak_mock):
        # Совместимость: помимо cookie принимается заголовок Authorization: Bearer
        _login(client, keycloak_mock)
        access_token = client.cookies.get(ACCESS_TOKEN_COOKIE)
        client.cookies.clear()

        response = client.get(ME_PATH, headers=bearer_headers(access_token))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()[EMAIL_KEY] == TEST_USER_1[EMAIL_KEY]

    def test_get_me_without_session(self, client):
        response = client.get(ME_PATH)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_me_with_invalid_token(self, client):
        response = client.get(ME_PATH, headers=bearer_headers("not-a-token"))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_callback_error_redirect_contains_no_tokens(client, keycloak_mock):
    # Ошибка входа: редирект на фронтенд с error во fragment, токенов в URL нет
    state = _start_login(client)
    response = _callback(client, code="unknown-code", state=state)

    fragment = urlparse(response.headers["location"]).fragment
    assert ERROR_KEY in parse_qs(fragment)
    assert ACCESS_TOKEN_COOKIE not in fragment
