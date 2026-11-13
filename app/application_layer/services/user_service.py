from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.across_layers.entities.token_info import TokenInfo
from app.across_layers.entities.user_entity import UserEntity
from app.across_layers.roles import ROLE_USER, ROLE_VIP_USER
from app.application_layer.contracts.keycloak_protocol import (
    KeycloakClientProtocol,
    KeycloakInvalidCredentialsError,
    KeycloakInvalidTokenError,
    KeycloakUserExistsError,
)
from app.application_layer.contracts.user_repository_protocol import UserRepositoryProtocol


class UserNotFoundError(Exception):
    pass


class UserAlreadyExistsError(Exception):
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
    # Эндпоинт backend'а, куда Keycloak возвращает браузер после входа через Google
    google_redirect_uri: str = "http://localhost:8000/api/v1/user/login/google/callback"
    # Alias identity provider'а Google в Keycloak (kc_idp_hint)
    google_idp_alias: str = "google"

    def build_google_login_url(self, state: str) -> str:
        """Строит URL входа через Google: страница авторизации Keycloak с kc_idp_hint.

        Браузер перенаправляется на этот URL; Keycloak сразу ведёт на форму
        входа Google, минуя собственную страницу логина.

        Args:
            state: случайная строка защиты от CSRF; Keycloak вернёт её в callback.

        Returns:
            Абсолютный URL авторизации Keycloak.
        """
        return self.keycloak.build_authorization_url(
            redirect_uri=self.google_redirect_uri,
            state=state,
            idp_alias=self.google_idp_alias,
        )

    async def get_user_by_id(self, user_id: int) -> UserEntity:
        """Возвращает пользователя по идентификатору.

        Args:
            user_id: идентификатор пользователя.

        Returns:
            Найденный пользователь.

        Raises:
            UserNotFoundError: пользователь с таким идентификатором не найден.
        """
        user = await self.repository.get_user_by_id(user_id)
        if user is None:
            raise UserNotFoundError("Пользователь не найден!")
        return user

    async def get_user_by_email(self, email: str) -> UserEntity:
        """Возвращает пользователя по email.

        Args:
            email: адрес электронной почты пользователя.

        Returns:
            Найденный пользователь.

        Raises:
            UserNotFoundError: пользователь с таким email не найден.
        """
        user = await self.repository.get_user_by_email(email)
        if user is None:
            raise UserNotFoundError("Пользователь не найден!")
        return user

    async def register_user(self, username: str, email: str, password: str) -> AuthResult:
        """Регистрирует нового пользователя и сразу аутентифицирует его.

        Пароль и роль сохраняются в Keycloak; в локальной БД остаётся только
        профиль (имя, email) со ссылкой на пользователя Keycloak. После успешной
        регистрации выполняется вход, чтобы клиент сразу получил JWT сессии.

        Args:
            username: отображаемое имя пользователя.
            email: адрес электронной почты, используется как логин.
            password: пароль в открытом виде, передаётся только в Keycloak.

        Returns:
            Созданный пользователь и JWT-токены сессии, выпущенные Keycloak.

        Raises:
            UserAlreadyExistsError: пользователь с таким email уже существует.
        """
        if await self.repository.get_user_by_email(email):
            raise UserAlreadyExistsError("Пользователь с таким email уже существует!")

        try:
            keycloak_id = await self.keycloak.create_user(
                username=username,
                email=email,
                password=password,
            )
        except KeycloakUserExistsError as e:
            raise UserAlreadyExistsError("Пользователь с таким email уже существует!") from e

        try:
            user = await self.repository.create_user(
                username=username,
                email=email,
                keycloak_id=keycloak_id,
            )
        except IntegrityError as e:
            # Компенсация: удаляем пользователя из Keycloak, чтобы не осталась запись-сирота
            await self.keycloak.delete_user(keycloak_id)
            raise UserAlreadyExistsError("Пользователь с таким email уже существует!") from e

        # Автоматический вход после регистрации: пароль только что проверен Keycloak
        token = await self.keycloak.authenticate(email=email, password=password)
        return AuthResult(user=user, token=token)

    async def login_user(self, email: str, password: str) -> AuthResult:
        """Аутентифицирует пользователя через Keycloak и возвращает токен сессии.

        Args:
            email: адрес электронной почты, указанный при регистрации.
            password: пароль в открытом виде, проверяется Keycloak.

        Returns:
            Пользователь и JWT-токены сессии, выпущенные Keycloak.

        Raises:
            InvalidCredentialsError: пользователь не найден или пароль не совпал.
        """
        try:
            token = await self.keycloak.authenticate(email=email, password=password)
        except KeycloakInvalidCredentialsError as e:
            raise InvalidCredentialsError("Неправильный пароль или логин!") from e

        user = await self.repository.get_user_by_email(email)
        if user is None:
            # Keycloak подтвердил пароль, но локального профиля нет — данные рассинхронизированы
            raise InvalidCredentialsError("Неправильный пароль или логин!")

        return AuthResult(user=user, token=token)

    async def login_with_google(self, code: str) -> AuthResult:
        """Завершает вход через Google: обменивает код авторизации на сессию.

        Браузер приходит на callback backend'а с кодом от Keycloak после входа
        в Google. Пользователь, вошедший впервые, создан брокером Keycloak мимо
        backend'а: локального профиля у него ещё нет — создаём его по данным
        из JWT (sub, email). Если email совпадает с уже зарегистрированным
        пользователем, выполняется вход в существующий аккаунт.

        Args:
            code: одноразовый код авторизации из query-параметра callback'а.

        Returns:
            Пользователь и JWT-токены сессии, выпущенные Keycloak.

        Raises:
            InvalidCredentialsError: код отклонён или Google не вернул email.
        """
        try:
            token = await self.keycloak.exchange_code(
                code=code,
                redirect_uri=self.google_redirect_uri,
            )
        except KeycloakInvalidCredentialsError as e:
            raise InvalidCredentialsError("Не удалось войти через Google!") from e

        payload = await self.keycloak.validate_token(token.access_token)
        if not payload.email:
            raise InvalidCredentialsError("Google не вернул email пользователя!")

        user = await self.repository.get_user_by_email(payload.email)
        if user is None:
            user = await self.repository.create_user(
                # Имя из профиля Google; если его нет — локальная часть email
                username=payload.full_name or _username_from_email(payload.email),
                email=payload.email,
                keycloak_id=payload.sub,
            )

        if ROLE_USER not in payload.roles:
            # Пользователь создан брокером, роль назначена не была. Как и при
            # подписке, в уже выданный токен она не попадёт — нужен повторный вход
            await self.keycloak.assign_role(payload.sub, ROLE_USER)

        return AuthResult(user=user, token=token)

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
            refresh_token: refresh-токен, выданный при входе или регистрации.

        Raises:
            InvalidTokenError: токен недействителен или сессия уже завершена.
        """
        try:
            await self.keycloak.logout(refresh_token=refresh_token)
        except KeycloakInvalidTokenError as e:
            raise InvalidTokenError("Сессия уже завершена или токен недействителен!") from e
