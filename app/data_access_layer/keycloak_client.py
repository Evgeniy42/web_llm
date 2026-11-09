import time

import httpx

from app.across_layers.entities.token_info import TokenInfo
from app.application_layer.contracts.keycloak_protocol import (
    KeycloakClientProtocol,
    KeycloakError,
    KeycloakInvalidCredentialsError,
    KeycloakInvalidTokenError,
    KeycloakUserExistsError,
)

# Запас до истечения сервисного токена, чтобы не уйти в запрос с почти протухшим токеном
_TOKEN_EXPIRY_MARGIN_SECONDS = 10


class KeycloakClient(KeycloakClientProtocol):
    """HTTP-клиент Keycloak: Admin REST API управляет пользователями, OIDC token endpoint выполняет вход.

    Пароль пользователя за пределы Keycloak не сохраняется: при регистрации он
    передаётся в credentials пользователя, при входе — в grant password, и по
    ответу Keycloak выдаётся JWT сессии.
    """

    def __init__(
        self,
        base_url: str,
        realm: str,
        client_id: str,
        client_secret: str,
        default_role: str = "user",
        timeout: float = 10.0,
    ) -> None:
        self._realm = realm
        self._client_id = client_id
        self._client_secret = client_secret
        self._default_role = default_role
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._service_token: str | None = None
        self._service_token_expires_at: float = 0.0

    async def create_user(self, username: str, email: str, password: str) -> str:
        """Создаёт пользователя в Keycloak с паролем и realm-ролью по умолчанию.

        Returns:
            Идентификатор созданного пользователя в Keycloak (UUID).

        Raises:
            KeycloakUserExistsError: пользователь с таким email уже существует.
            KeycloakError: Keycloak вернул ошибку или недоступен.
        """
        response = await self._client.post(
            f"/admin/realms/{self._realm}/users",
            headers=await self._admin_headers(),
            json={
                # Логином в Keycloak служит email (registrationEmailAsUsername в realm)
                "username": email,
                "email": email,
                "enabled": True,
                "emailVerified": True,
                # firstName/lastName обязательны в user profile Keycloak 26:
                # без них при входе срабатывает required action VERIFY_PROFILE
                "firstName": username,
                "lastName": username,
                "credentials": [{"type": "password", "value": password, "temporary": False}],
            },
        )
        if response.status_code == 409:
            raise KeycloakUserExistsError(f"Пользователь с email '{email}' уже существует в Keycloak")
        if response.status_code != 201:
            raise KeycloakError(
                f"Keycloak не создал пользователя: HTTP {response.status_code}: {response.text}"
            )

        keycloak_id = response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
        await self._assign_realm_role(keycloak_id, self._default_role)
        return keycloak_id

    async def authenticate(self, email: str, password: str) -> TokenInfo:
        """Проверяет логин/пароль через grant password и возвращает токены Keycloak.

        Raises:
            KeycloakInvalidCredentialsError: пара логин/пароль отклонена.
            KeycloakError: Keycloak вернул ошибку или недоступен.
        """
        response = await self._client.post(
            f"/realms/{self._realm}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "username": email,
                "password": password,
            },
        )
        # Keycloak отвечает 400 (invalid_grant) или 401 на неверную пару логин/пароль
        if response.status_code in (400, 401):
            raise KeycloakInvalidCredentialsError("Keycloak отклонил логин или пароль")
        if response.status_code != 200:
            raise KeycloakError(
                f"Keycloak не выдал токен: HTTP {response.status_code}: {response.text}"
            )

        payload = response.json()
        return TokenInfo(
            access_token=payload["access_token"],
            token_type=payload.get("token_type", "Bearer"),
            expires_in=payload.get("expires_in", 0),
            refresh_token=payload.get("refresh_token"),
        )

    async def logout(self, refresh_token: str) -> None:
        """Завершает сессию пользователя: отзывает refresh-токен и сессию Keycloak.

        Access-токен остаётся валидным до своего expires_in — это ограничение
        stateless JWT; revoke происходит для refresh-токена и SSO-сессии.

        Raises:
            KeycloakInvalidTokenError: refresh-токен отклонён Keycloak.
            KeycloakError: Keycloak вернул ошибку или недоступен.
        """
        response = await self._client.post(
            f"/realms/{self._realm}/protocol/openid-connect/logout",
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": refresh_token,
            },
        )
        # Невалидный или уже отозванный refresh-токен Keycloak отклоняет с 400
        if response.status_code == 400:
            raise KeycloakInvalidTokenError("Keycloak отклонил refresh-токен")
        if response.status_code != 204:
            raise KeycloakError(
                f"Keycloak не выполнил logout: HTTP {response.status_code}: {response.text}"
            )

    async def delete_user(self, keycloak_id: str) -> None:
        """Удаляет пользователя из Keycloak (компенсация при откате регистрации)."""
        response = await self._client.delete(
            f"/admin/realms/{self._realm}/users/{keycloak_id}",
            headers=await self._admin_headers(),
        )
        if response.status_code not in (204, 404):
            raise KeycloakError(
                f"Keycloak не удалил пользователя {keycloak_id}: HTTP {response.status_code}: {response.text}"
            )

    async def close(self) -> None:
        """Закрывает HTTP-клиент и освобождает соединения."""
        await self._client.aclose()

    async def _get_service_account_token(self) -> str:
        """Возвращает кешированный access-token сервисного аккаунта (client_credentials)."""
        if self._service_token and time.monotonic() < self._service_token_expires_at:
            return self._service_token

        response = await self._client.post(
            f"/realms/{self._realm}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                # С Keycloak 26.8.2 Admin REST API принимает только токены со scope kc-admin-api;
                # scope опциональный у клиента и запрашивается явно только для service account
                "scope": "kc-admin-api",
            },
        )
        if response.status_code != 200:
            raise KeycloakError(
                f"Keycloak не выдал токен сервисного аккаунта: HTTP {response.status_code}: {response.text}"
            )

        payload = response.json()
        self._service_token = payload["access_token"]
        self._service_token_expires_at = (
            time.monotonic() + payload.get("expires_in", 60) - _TOKEN_EXPIRY_MARGIN_SECONDS
        )
        return self._service_token

    async def _admin_headers(self) -> dict[str, str]:
        token = await self._get_service_account_token()
        return {"Authorization": f"Bearer {token}"}

    async def _assign_realm_role(self, keycloak_id: str, role_name: str) -> None:
        """Назначает пользователю realm-роль."""
        headers = await self._admin_headers()
        role_response = await self._client.get(
            f"/admin/realms/{self._realm}/roles/{role_name}",
            headers=headers,
        )
        if role_response.status_code != 200:
            raise KeycloakError(f"Роль '{role_name}' не найдена в realm '{self._realm}'")

        mapping_response = await self._client.post(
            f"/admin/realms/{self._realm}/users/{keycloak_id}/role-mappings/realm",
            headers=headers,
            json=[role_response.json()],
        )
        if mapping_response.status_code != 204:
            raise KeycloakError(
                f"Keycloak не назначил роль '{role_name}' пользователю {keycloak_id}: "
                f"HTTP {mapping_response.status_code}: {mapping_response.text}"
            )
