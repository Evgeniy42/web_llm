import logging
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.across_layers.entities.token_info import TokenInfo
from app.across_layers.entities.token_payload import TokenPayload
from app.across_layers.entities.user_entity import UserEntity
from app.across_layers.roles import ROLE_USER, ROLE_VIP_USER
from app.application_layer.contracts.client_contracts.keycloak_protocol import (
    KeycloakClientProtocol,
    KeycloakInvalidCredentialsError,
    KeycloakInvalidTokenError,
)
from app.application_layer.contracts.service_contracts.user_repository_protocol import UserRepositoryProtocol

logger = logging.getLogger(__name__)


class UserNotFoundError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidTokenError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AuthResult:
    """Результат успешной аутентификации: профиль пользователя и токен сессии Keycloak."""

    user: UserEntity
    token: TokenInfo


def _username_from_email(email: str) -> str:
    """Выводит имя профиля из email для пользователей, созданных через соцсеть.

    Google не передаёт отображаемое имя нашего приложения, поэтому берётся
    локальная часть email. Ограничения — из UserModel: VARCHAR(50), без unique.
    """
    local = email.split("@", 1)[0].strip()
    if len(local) < 3:
        local = f"user_{local}"
    return local[:50]


@dataclass(slots=True)
class UserService:
    repository: UserRepositoryProtocol
    keycloak: KeycloakClientProtocol
    # Эндпоинт backend'а, куда Keycloak возвращает браузер после входа (единый callback)
    redirect_uri: str = "http://localhost:8000/api/v1/user/login/callback"
    # Alias identity provider'а Google в Keycloak (kc_idp_hint)
    google_idp_alias: str = "google"

    def build_login_url(self, state: str, code_challenge: str, idp_alias: str | None = None) -> str:
        """Строит URL страницы входа Keycloak для браузера (authorization code flow + PKCE).

        Без idp_alias Keycloak показывает собственную страницу логина
        (логин/пароль и ссылка на регистрацию); с idp_alias=google — сразу
        перенаправляет на форму входа Google.

        Args:
            state: случайная строка защиты от CSRF; Keycloak вернёт её в callback.
            code_challenge: PKCE-челлендж (S256), привязанный к той же попытке входа.
            idp_alias: alias identity provider'а (kc_idp_hint) или None.

        Returns:
            Абсолютный URL авторизации Keycloak.
        """
        return self.keycloak.build_authorization_url(
            redirect_uri=self.redirect_uri,
            state=state,
            code_challenge=code_challenge,
            idp_alias=idp_alias,
        )

    async def complete_login(self, code: str, code_verifier: str) -> AuthResult:
        """Завершает вход: обменивает код авторизации на сессию и профиль пользователя.

        Браузер приходит на callback backend'а с кодом от Keycloak после входа
        (форма Keycloak или Google). Пользователь, вошедший впервые, создан
        Keycloak мимо backend'а: локального профиля у него ещё нет — создаём
        его по данным из проверенного JWT. Профиль ищется только по sub
        (keycloak_id): email может меняться и расходиться в регистре.

        Args:
            code: одноразовый код авторизации из query-параметра callback'а.
            code_verifier: PKCE-verifier из cookie попытки входа.

        Returns:
            Пользователь и JWT-токены сессии, выпущенные Keycloak.

        Raises:
            InvalidCredentialsError: код отклонён или Keycloak не вернул email.
        """
        try:
            token = await self.keycloak.exchange_code(
                code=code,
                redirect_uri=self.redirect_uri,
                code_verifier=code_verifier,
            )
        except KeycloakInvalidCredentialsError as e:
            raise InvalidCredentialsError("Не удалось завершить вход: код авторизации отклонён!") from e

        payload = await self.keycloak.validate_token(token.access_token)
        if not payload.email:
            raise InvalidCredentialsError("Keycloak не вернул email пользователя!")

        user = await self.repository.get_user_by_keycloak_id(payload.sub)
        if user is None:
            user = await self._create_profile(payload)

        if ROLE_USER not in payload.roles:
            # Пользователь создан Keycloak мимо backend'а и почему-то без базовой
            # роли. Сбой назначения не должен ронять вход: роль назначится при
            # следующем логине. В уже выданный токен она не попадёт в любом случае.
            try:
                await self.keycloak.assign_role(payload.sub, ROLE_USER)
            except Exception:
                logger.exception("Не удалось назначить роль '%s' пользователю %s", ROLE_USER, payload.sub)

        return AuthResult(user=user, token=token)

    async def get_user_by_keycloak_id(self, keycloak_id: str) -> UserEntity:
        """Возвращает пользователя по идентификатору Keycloak (sub из JWT).

        Args:
            keycloak_id: идентификатор пользователя в Keycloak (UUID).

        Returns:
            Найденный пользователь.

        Raises:
            UserNotFoundError: локальный профиль для этого keycloak_id не найден.
        """
        user = await self.repository.get_user_by_keycloak_id(keycloak_id)
        if user is None:
            raise UserNotFoundError("Пользователь не найден!")
        return user

    async def grant_subscription(self, keycloak_id: str) -> None:
        """Оформляет подписку: назначает пользователю роль vip_user в Keycloak.

        Имитация оплаты: проверки платежа нет. Роль назначается сразу, но в JWT
        она попадёт только после повторного входа — роли зашиты в выданный токен.

        Args:
            keycloak_id: идентификатор пользователя в Keycloak (sub из JWT).
        """
        await self.keycloak.assign_role(keycloak_id, ROLE_VIP_USER)

    async def logout_user(self, refresh_token: str) -> None:
        """Завершает сессию пользователя, отзывая refresh-токен в Keycloak.

        Args:
            refresh_token: refresh-токен из сессионной cookie.

        Raises:
            InvalidTokenError: токен недействителен или сессия уже завершена.
        """
        try:
            await self.keycloak.logout(refresh_token=refresh_token)
        except KeycloakInvalidTokenError as e:
            raise InvalidTokenError("Сессия уже завершена или токен недействителен!") from e

    async def _create_profile(self, payload: TokenPayload) -> UserEntity:
        """Создаёт локальный профиль при первом входе (идемпотентно).

        При гонке параллельных первых входов один из запросов упирается в
        unique-ограничение keycloak_id: читаем уже созданный профиль и
        продолжаем вход.
        """
        try:
            return await self.repository.create_user(
                # Имя из профиля identity provider'а; если его нет — локальная часть email
                username=payload.full_name or _username_from_email(payload.email or ""),
                email=payload.email or "",
                keycloak_id=payload.sub,
            )
        except IntegrityError:
            user = await self.repository.get_user_by_keycloak_id(payload.sub)
            if user is None:
                raise
            return user
