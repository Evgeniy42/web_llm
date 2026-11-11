from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.across_layers.entities.token_info import TokenInfo
from app.across_layers.entities.user_entity import UserEntity
from app.across_layers.roles import ROLE_VIP_USER
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


@dataclass(slots=True)
class UserService:
    repository: UserRepositoryProtocol
    keycloak: KeycloakClientProtocol

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
