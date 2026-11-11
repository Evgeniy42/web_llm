"""Моковые значения и фабрики для unit-тестов и интеграционных API-тестов."""

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
    KeycloakUserExistsError,
)

# Повторяющиеся тестовые значения
USER_ID = 1
NONEXISTENT_USER_ID = 999
TEST_USERNAME = "testuser"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "password123"
KEYCLOAK_USER_ID = "00000000-0000-0000-0000-000000000001"

# Значения токена Keycloak
ACCESS_TOKEN = "mock-access-token"
REFRESH_TOKEN = "mock-refresh-token"
TOKEN_TYPE = "Bearer"
EXPIRES_IN = 3600

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


class MockKeycloakClient(KeycloakClientProtocol):
    """In-memory заглушка Keycloak для тестов без контейнера Keycloak.

    Поведение повторяет контракт: дубликат email при создании -> KeycloakUserExistsError,
    неверная пара логин/пароль -> KeycloakInvalidCredentialsError,
    невалидный или отозванный refresh-токен -> KeycloakInvalidTokenError.
    Роли хранятся у пользователя, а в access-токен попадают снимком при входе —
    как в JWT настоящего Keycloak: назначенная после входа роль появится
    в токене только после повторной аутентификации.
    """

    def __init__(self) -> None:
        self._users: dict[str, dict] = {}
        self._refresh_tokens: set[str] = set()
        self._revoked_refresh_tokens: set[str] = set()
        # access_token -> снимок полезной нагрузки на момент входа (как в JWT)
        self._access_tokens: dict[str, TokenPayload] = {}

    async def create_user(self, username: str, email: str, password: str) -> str:
        if email in self._users:
            raise KeycloakUserExistsError(f"Пользователь с email '{email}' уже существует в Keycloak")
        keycloak_id = str(uuid4())
        self._users[email] = {"id": keycloak_id, "password": password, "roles": {ROLE_USER}}
        return keycloak_id

    async def authenticate(self, email: str, password: str) -> TokenInfo:
        user = self._users.get(email)
        if user is None or user["password"] != password:
            raise KeycloakInvalidCredentialsError("Keycloak отклонил логин или пароль")
        refresh_token = f"{REFRESH_TOKEN}-{email}-{uuid4()}"
        self._refresh_tokens.add(refresh_token)
        access_token = f"{ACCESS_TOKEN}-{email}-{uuid4()}"
        self._access_tokens[access_token] = TokenPayload(
            sub=user["id"],
            email=email,
            roles=frozenset(user["roles"]),
        )
        return TokenInfo(
            access_token=access_token,
            token_type=TOKEN_TYPE,
            expires_in=EXPIRES_IN,
            refresh_token=refresh_token,
        )

    async def logout(self, refresh_token: str) -> None:
        # Как настоящий Keycloak: повторный logout с отозванным токеном идемпотентен (204),
        # а совсем чужой/битый токен отклоняется (400)
        if refresh_token in self._revoked_refresh_tokens:
            return
        if refresh_token not in self._refresh_tokens:
            raise KeycloakInvalidTokenError("Keycloak отклонил refresh-токен")
        self._refresh_tokens.discard(refresh_token)
        self._revoked_refresh_tokens.add(refresh_token)

    async def delete_user(self, keycloak_id: str) -> None:
        for email, data in list(self._users.items()):
            if data["id"] == keycloak_id:
                del self._users[email]
                return

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
