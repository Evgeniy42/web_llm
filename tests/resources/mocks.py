"""Моковые значения и фабрики для unit-тестов и интеграционных API-тестов."""

import base64
import hashlib
from urllib.parse import urlencode
from uuid import uuid4

from app.across_layers.entities.token_info import TokenInfo
from app.across_layers.entities.token_payload import TokenPayload
from app.across_layers.entities.user_entity import UserEntity
from app.across_layers.roles import ROLE_USER
from app.application_layer.contracts.keycloak_protocol import (
    KeycloakClientProtocol,
    KeycloakError,
    KeycloakInvalidCredentialsError,
    KeycloakInvalidTokenError,
)

# Повторяющиеся тестовые значения
USER_ID = 1
TEST_USERNAME = "testuser"
TEST_EMAIL = "test@example.com"
KEYCLOAK_USER_ID = "00000000-0000-0000-0000-000000000001"

# Значения токена Keycloak
ACCESS_TOKEN = "mock-access-token"
REFRESH_TOKEN = "mock-refresh-token"
TOKEN_TYPE = "Bearer"
EXPIRES_IN = 3600

# Значения для входа через Keycloak (authorization code flow + PKCE)
REDIRECT_URI = "http://localhost:8000/api/v1/user/login/callback"
GOOGLE_IDP_ALIAS = "google"
KEYCLOAK_AUTH_URL = "https://keycloak.test/realms/web-llm/protocol/openid-connect/auth"
AUTH_CODE_PREFIX = "mock-auth-code"

# Значения для ChatService
USER_MESSAGE = "Hello"
LLM_RESPONSE = "Привет!"


def make_user_entity() -> UserEntity:
    return UserEntity(id=USER_ID, username=TEST_USERNAME, email=TEST_EMAIL)


def make_token_info() -> TokenInfo:
    return TokenInfo(
        access_token=ACCESS_TOKEN,
        token_type=TOKEN_TYPE,
        expires_in=EXPIRES_IN,
        refresh_token=REFRESH_TOKEN,
    )


def make_code_challenge(code_verifier: str) -> str:
    """PKCE-челлендж S256 из verifier'а — та же формула, что в user_router."""
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class MockKeycloakClient(KeycloakClientProtocol):
    """In-memory заглушка Keycloak для тестов без контейнера Keycloak.

    Поведение повторяет контракт authorization code flow + PKCE: код
    авторизации одноразовый, обмен требует redirect_uri и verifier,
    соответствующий challenge из запроса авторизации. Невалидный или
    отозванный refresh-токен -> KeycloakInvalidTokenError. Роли хранятся
    у пользователя, а в access-токен попадают снимком при входе — как в JWT
    настоящего Keycloak: назначенная после входа роль появится в токене
    только после повторной аутентификации.

    Связывание Google-аккаунта с существующим пользователем в настоящем
    Keycloak выполняется самим Keycloak с подтверждением владельца. Мок
    моделирует уже ЗАВЕРШЁННОЕ связывание: код авторизации для email,
    который уже есть в моке, возвращает sub того же пользователя.
    """

    def __init__(self) -> None:
        # email -> {"id": sub, "roles": set[str], "full_name": str | None}
        self._users: dict[str, dict] = {}
        self._refresh_tokens: set[str] = set()
        self._revoked_refresh_tokens: set[str] = set()
        # access_token -> снимок полезной нагрузки на момент входа (как в JWT)
        self._access_tokens: dict[str, TokenPayload] = {}
        # code -> email пользователя, завершившего вход на странице Keycloak
        self._auth_codes: dict[str, str] = {}
        # PKCE: code_challenge -> redirect_uri из запросов авторизации
        self._code_challenges: dict[str, str] = {}

    def register_user(self, email: str, full_name: str | None = None, with_default_role: bool = True) -> str:
        """Создаёт пользователя в моке Keycloak и возвращает его sub.

        Эквивалент регистрации на странице Keycloak или создания пользователя
        брокером Google: оба пути проходят мимо backend'а. Базовая роль user
        назначается сразу — как default role realm'а в настоящем Keycloak;
        with_default_role=False моделирует пользователя без неё (роль
        доназначит backend при первом входе).

        Args:
            email: адрес электронной почты (логин) пользователя.
            full_name: имя из профиля Google (claim name в выданном токене).
            with_default_role: назначить ли realm-роль user при создании.

        Returns:
            Идентификатор пользователя в моке Keycloak (sub будущего JWT).
        """
        user = self._users.get(email)
        if user is not None:
            return user["id"]
        keycloak_id = str(uuid4())
        roles = {ROLE_USER} if with_default_role else set()
        self._users[email] = {"id": keycloak_id, "roles": roles, "full_name": full_name}
        return keycloak_id

    def issue_auth_code(self, email: str) -> str:
        """Выдаёт одноразовый код авторизации для callback'а backend'а.

        Args:
            email: адрес пользователя, завершившего вход на странице Keycloak.

        Returns:
            Код авторизации для query-параметра code callback'а.
        """
        if email not in self._users:
            raise AssertionError(f"Пользователь {email} не создан в моке: вызовите register_user")
        code = f"{AUTH_CODE_PREFIX}-{uuid4()}"
        self._auth_codes[code] = email
        return code

    def add_user_with_code(self, email: str, full_name: str | None = None) -> str:
        """Создаёт пользователя (если его нет) и сразу возвращает код авторизации.

        Args:
            email: адрес электронной почты пользователя.
            full_name: имя из профиля Google (claim name в выданном токене).

        Returns:
            Код авторизации для вызова callback'а (query-параметр code).
        """
        self.register_user(email, full_name)
        return self.issue_auth_code(email)

    def build_authorization_url(
        self,
        redirect_uri: str,
        state: str,
        code_challenge: str,
        idp_alias: str | None = None,
    ) -> str:
        # Challenge запоминается: при обмене кода verifier должен ему соответствовать
        self._code_challenges[code_challenge] = redirect_uri
        query = {
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if idp_alias:
            query["kc_idp_hint"] = idp_alias
        return f"{KEYCLOAK_AUTH_URL}?{urlencode(query)}"

    async def exchange_code(self, code: str, redirect_uri: str, code_verifier: str) -> TokenInfo:
        # Код одноразовый: pop при первом же обмене, как в настоящем Keycloak
        email = self._auth_codes.pop(code, None)
        # PKCE: verifier должен соответствовать challenge какой-либо попытки входа,
        # а redirect_uri — совпасть с тем, что был в запросе авторизации
        expected_redirect = self._code_challenges.pop(make_code_challenge(code_verifier), None)
        if email is None or expected_redirect is None or expected_redirect != redirect_uri:
            raise KeycloakInvalidCredentialsError("Keycloak отклонил код авторизации")
        return self._issue_token(email, self._users[email])

    async def logout(self, refresh_token: str) -> None:
        # Как настоящий Keycloak: повторный logout с отозванным токеном идемпотентен (204),
        # а совсем чужой/битый токен отклоняется (400)
        if refresh_token in self._revoked_refresh_tokens:
            return
        if refresh_token not in self._refresh_tokens:
            raise KeycloakInvalidTokenError("Keycloak отклонил refresh-токен")
        self._refresh_tokens.discard(refresh_token)
        self._revoked_refresh_tokens.add(refresh_token)

    async def validate_token(self, access_token: str) -> TokenPayload:
        payload = self._access_tokens.get(access_token)
        if payload is None:
            raise KeycloakInvalidTokenError("Keycloak отклонил access-токен")
        return payload

    async def assign_role(self, keycloak_id: str, role_name: str) -> None:
        for data in self._users.values():
            if data["id"] == keycloak_id:
                data["roles"].add(role_name)
                return
        raise KeycloakError(f"Пользователь {keycloak_id} не найден в Keycloak")

    async def close(self) -> None:
        pass

    def reset(self) -> None:
        self._users.clear()
        self._refresh_tokens.clear()
        self._revoked_refresh_tokens.clear()
        self._access_tokens.clear()
        self._auth_codes.clear()
        self._code_challenges.clear()

    def _issue_token(self, email: str, user: dict) -> TokenInfo:
        """Выпускает токены сессии со снимком ролей пользователя (как JWT Keycloak).

        Токены содержат только cookie-safe символы (RFC 6265), как base64url
        настоящих JWT. Email в строку не встраивается: '@' не входит в разрешённый
        набор http.cookies, и backend обернул бы значение Set-Cookie в кавычки —
        тесты, читающие токен из cookie для Bearer-заголовка, получали бы кавычки
        в значении и ловили 401.
        """
        refresh_token = f"{REFRESH_TOKEN}-{uuid4()}"
        self._refresh_tokens.add(refresh_token)
        access_token = f"{ACCESS_TOKEN}-{uuid4()}"
        self._access_tokens[access_token] = TokenPayload(
            sub=user["id"],
            email=email,
            roles=frozenset(user["roles"]),
            full_name=user.get("full_name"),
        )
        return TokenInfo(
            access_token=access_token,
            token_type=TOKEN_TYPE,
            expires_in=EXPIRES_IN,
            refresh_token=refresh_token,
        )
