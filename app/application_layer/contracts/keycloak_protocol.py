from typing import Protocol

from app.across_layers.entities.token_info import TokenInfo


class KeycloakError(Exception):
    """Базовая ошибка обращения к Keycloak."""


class KeycloakUserExistsError(KeycloakError):
    """Пользователь с таким логином уже существует в Keycloak."""


class KeycloakInvalidCredentialsError(KeycloakError):
    """Keycloak отклонил пару логин/пароль."""


class KeycloakInvalidTokenError(KeycloakError):
    """Keycloak отклонил токен (недействителен, истёк или уже отозван)."""


class KeycloakClientProtocol(Protocol):
    """Контракт взаимодействия с Keycloak.

    Keycloak — единственное хранилище паролей и ролей пользователей;
    обращается к нему только серверная часть.
    """

    async def create_user(self, username: str, email: str, password: str) -> str: ...

    async def authenticate(self, email: str, password: str) -> TokenInfo: ...

    async def logout(self, refresh_token: str) -> None: ...

    async def delete_user(self, keycloak_id: str) -> None: ...

    async def close(self) -> None: ...
