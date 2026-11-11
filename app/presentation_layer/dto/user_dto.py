from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

UsernameStr = Annotated[str, StringConstraints(min_length=3, max_length=50, strip_whitespace=True)]
PasswordStr = Annotated[str, StringConstraints(min_length=8)]


class UserRegisterRequestDTO(BaseModel):
    """Данные запроса на регистрацию пользователя."""

    model_config = ConfigDict(extra="forbid")

    username: UsernameStr = Field(description="Отображаемое имя пользователя, 3-50 символов")
    email: EmailStr = Field(description="Адрес электронной почты, используется как логин")
    password: PasswordStr = Field(description="Пароль, минимум 8 символов")


class UserLoginRequestDTO(BaseModel):
    """Данные запроса на вход пользователя."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(description="Адрес электронной почты, указанный при регистрации")
    password: str = Field(description="Пароль пользователя")


class UserLogoutRequestDTO(BaseModel):
    """Данные запроса на выход из сессии."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(description="Refresh-токен, полученный при входе или регистрации")


class UserResponseDTO(BaseModel):
    """Данные пользователя в ответах API."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Идентификатор пользователя")
    username: str = Field(description="Отображаемое имя пользователя")
    email: EmailStr = Field(description="Адрес электронной почты")


class SubscriptionResponseDTO(BaseModel):
    """Ответ на запрос оформления подписки (имитация оплаты)."""

    message: str = Field(description="Текст подтверждения оформления подписки")


class UserAuthResponseDTO(BaseModel):
    """Ответ на успешную регистрацию или вход: профиль пользователя и JWT сессии, выпущенный Keycloak."""

    id: int = Field(description="Идентификатор пользователя")
    username: str = Field(description="Отображаемое имя пользователя")
    email: EmailStr = Field(description="Адрес электронной почты")
    access_token: str = Field(description="JWT доступа; передаётся в заголовке Authorization: Bearer")
    token_type: str = Field(description="Тип токена (Bearer)")
    expires_in: int = Field(description="Время жизни access-токена в секундах")
    refresh_token: str | None = Field(default=None, description="Токен обновления сессии, если выдан")
