import time
from urllib.parse import urlencode

import httpx
import jwt

from app.across_layers.entities.token_info import TokenInfo
from app.across_layers.entities.token_payload import TokenPayload
from app.application_layer.contracts.client_contracts.keycloak_protocol import (
    KeycloakClientProtocol,
    KeycloakError,
    KeycloakInvalidCredentialsError,
    KeycloakInvalidTokenError,
)

# Запас до истечения сервисного токена, чтобы не уйти в запрос с почти протухшим токеном
_TOKEN_EXPIRY_MARGIN_SECONDS = 10


class KeycloakClient(KeycloakClientProtocol):
    """HTTP-клиент Keycloak: OIDC authorization code flow (PKCE) и Admin REST API для ролей.

    Пароли пользователей через backend не проходят: ввод логина/пароля и
    регистрация выполняются на странице Keycloak, а backend лишь строит
    authorization URL, обменивает код на токены (с PKCE-verifier) и
    валидирует выпущенные JWT.
    """

    def __init__(
        self,
        base_url: str,
        realm: str,
        client_id: str,
        client_secret: str,
        public_url: str | None = None,
        audience: str = "web-llm-api",
        timeout: float = 10.0,
    ) -> None:
        self._realm = realm
        self._client_id = client_id
        self._client_secret = client_secret
        # Аудитория, которой должен быть выпущен access-токен (claim aud);
        # добавляется в токен client scope'ом web-llm-api (oidc-audience-mapper в realm)
        self._audience = audience
        # Публичный адрес для редиректов браузера: base_url может указывать
        # во внутреннюю docker-сеть (http://keycloak:8080), недоступную снаружи
        self._public_url = (public_url or base_url).rstrip("/")
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._service_token: str | None = None
        self._service_token_expires_at: float = 0.0
        # JWKS realm'а: публичные ключи для проверки подписи JWT, кешируются
        self._jwks: dict | None = None

    def build_authorization_url(
        self,
        redirect_uri: str,
        state: str,
        code_challenge: str,
        idp_alias: str | None = None,
    ) -> str:
        """Строит URL страницы входа Keycloak для браузера (authorization code flow + PKCE).

        URL формируется от public_url: браузер не имеет доступа к внутреннему
        адресу Keycloak в docker-сети. redirect_uri должен быть внесён в
        Valid Redirect URIs клиента Keycloak, иначе Keycloak отклонит запрос.

        Args:
            redirect_uri: эндпоинт backend'а, куда Keycloak вернёт браузер с кодом.
            state: случайная строка защиты от CSRF; возвращается в callback без изменений.
            code_challenge: PKCE-челлендж (base64url(sha256(verifier)), метод S256);
                verifier хранится у backend'а и передаётся при обмене кода на токены.
            idp_alias: alias identity provider'а (kc_idp_hint) — Keycloak сразу
                перенаправляет на форму входа соцсети, минуя собственную страницу логина.

        Returns:
            Абсолютный URL, на который backend перенаправляет браузер пользователя.
        """
        query = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if idp_alias:
            query["kc_idp_hint"] = idp_alias
        base = f"{self._public_url}/realms/{self._realm}/protocol/openid-connect/auth"
        return f"{base}?{urlencode(query)}"

    async def exchange_code(self, code: str, redirect_uri: str, code_verifier: str) -> TokenInfo:
        """Обменивает код авторизации на токены сессии (authorization code flow + PKCE).

        Код выдаёт Keycloak после входа пользователя (форма Keycloak или
        identity provider, например Google) и возврата браузера на
        redirect_uri backend'а.

        Args:
            code: код авторизации из query-параметра callback'а.
            redirect_uri: тот же redirect_uri, что был в запросе авторизации,
                иначе Keycloak отклонит обмен.
            code_verifier: PKCE-verifier из cookie попытки входа; Keycloak сверит
                его хеш с code_challenge из запроса авторизации.

        Returns:
            Токены сессии, выпущенные Keycloak.

        Raises:
            KeycloakInvalidCredentialsError: код отклонён (истёк, уже использован,
                не совпал redirect_uri или PKCE-verifier).
            KeycloakError: Keycloak вернул ошибку или недоступен.
        """
        response = await self._client.post(
            f"/realms/{self._realm}/protocol/openid-connect/token",
            data={
                "grant_type": "authorization_code",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
        )
        # Код одноразовый и короткоживущий: повторное использование, истечение,
        # неверный redirect_uri и чужой code_verifier Keycloak отклоняет как invalid_grant (400)
        if response.status_code in (400, 401):
            raise KeycloakInvalidCredentialsError("Keycloak отклонил код авторизации")
        if response.status_code != 200:
            raise KeycloakError(
                f"Keycloak не выдал токен по коду авторизации: HTTP {response.status_code}: {response.text}"
            )

        return self._to_token_info(response.json())

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

    async def assign_role(self, keycloak_id: str, role_name: str) -> None:
        """Назначает пользователю realm-роль Keycloak.

        Идемпотентно на стороне Keycloak: повторное назначение той же роли
        не создаёт дубликатов в role-mappings.

        Args:
            keycloak_id: идентификатор пользователя в Keycloak (UUID, sub из JWT).
            role_name: имя realm-роли, описанной в realm.

        Raises:
            KeycloakError: роль не найдена в realm или Keycloak отклонил назначение.
        """
        await self._assign_realm_role(keycloak_id, role_name)

    async def validate_token(self, access_token: str) -> TokenPayload:
        """Проверяет JWT доступа и возвращает его полезную нагрузку.

        Подпись проверяется по JWKS realm'а (RS256, ключи кешируются и
        перечитываются при неизвестном kid — ротация ключей). Аудитория (aud)
        обязана содержать аудиторию Web LLM API: backend не принимает токены,
        выпущенные для других клиентов/сервисов. Claims exp, iat и sub
        обязательны, typ обязан быть "Bearer" — этим отсекаются refresh- и
        id-токены. Issuer сверяется вручную с двумя допустимыми адресами
        (внутренний base_url и публичный public_url). Роли извлекаются из
        claim `realm_access.roles`.

        Args:
            access_token: JWT доступа, полученный клиентом при входе.

        Returns:
            Идентификатор пользователя, email и набор realm-ролей из токена.

        Raises:
            KeycloakInvalidTokenError: токен битый, истёк, выпущен не для нашего
                API или подпись не сошлась.
            KeycloakError: Keycloak недоступен (не удалось получить JWKS).
        """
        try:
            kid = jwt.get_unverified_header(access_token).get("kid")
        except jwt.PyJWTError as e:
            raise KeycloakInvalidTokenError("Токен имеет неверный формат") from e

        key = await self._get_signing_key(kid)
        try:
            payload = jwt.decode(
                access_token,
                key=key,
                algorithms=["RS256"],
                audience=self._audience,
                # exp/iat/sub обязательны; issuer проверяется вручную ниже —
                # валидных значений два (см. комментарий)
                options={"require": ["exp", "iat", "sub"], "verify_iss": False},
            )
        except jwt.PyJWTError as e:
            raise KeycloakInvalidTokenError("Токен недействителен или истёк") from e

        # Принимаем только access-токены: у refresh/id-токенов Keycloak typ иной
        if payload.get("typ") != "Bearer":
            raise KeycloakInvalidTokenError("Токен недействителен или истёк")

        # Keycloak формирует iss по адресу, на который пришёл запрос: обмен кода
        # идёт из docker-сети (base_url), а issuer браузерного входа — публичный
        # адрес (public_url). Оба issuer'а наши, принимаем оба.
        expected_issuers = {
            f"{self._client.base_url}/realms/{self._realm}",
            f"{self._public_url}/realms/{self._realm}",
        }
        if payload.get("iss") not in expected_issuers:
            raise KeycloakInvalidTokenError("Токен недействителен или истёк")

        return TokenPayload(
            sub=payload["sub"],
            email=payload.get("email"),
            roles=frozenset(payload.get("realm_access", {}).get("roles", [])),
            # Имя из профиля Google (брокерский вход); при входе по паролю отсутствует
            full_name=payload.get("name") or payload.get("given_name"),
        )

    async def close(self) -> None:
        """Закрывает HTTP-клиент и освобождает соединения."""
        await self._client.aclose()

    @staticmethod
    def _to_token_info(payload: dict) -> TokenInfo:
        """Собирает TokenInfo из JSON-ответа token endpoint'а Keycloak."""
        return TokenInfo(
            access_token=payload["access_token"],
            token_type=payload.get("token_type", "Bearer"),
            expires_in=payload.get("expires_in", 0),
            refresh_token=payload.get("refresh_token"),
        )

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

    async def _get_signing_key(self, kid: str | None) -> jwt.PyJWK:
        """Возвращает публичный ключ подписи JWT по kid из JWKS realm'а.

        При неизвестном kid JWKS перечитывается один раз (ротация ключей),
        прежде чем токен будет окончательно отклонён.
        """
        for force_refresh in (False, True):
            jwks = await self._get_jwks(force_refresh=force_refresh)
            jwk = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
            if jwk is not None:
                return jwt.PyJWK(jwk)
        raise KeycloakInvalidTokenError("Ключ подписи токена не найден в JWKS realm'а")

    async def _get_jwks(self, force_refresh: bool = False) -> dict:
        """Возвращает кешированный JWKS realm'а или запрашивает его у Keycloak."""
        if self._jwks is not None and not force_refresh:
            return self._jwks

        response = await self._client.get(
            f"/realms/{self._realm}/protocol/openid-connect/certs",
        )
        if response.status_code != 200:
            raise KeycloakError(
                f"Keycloak не вернул JWKS: HTTP {response.status_code}: {response.text}"
            )
        self._jwks = response.json()
        return self._jwks
