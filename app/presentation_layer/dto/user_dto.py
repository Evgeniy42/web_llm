from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponseDTO(BaseModel):
    """Профиль текущего пользователя в ответе GET /user/me.

    Роли берутся из валидированного JWT (фронтенд не декодирует токен,
    а роли нужны ему для отображения UI).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Идентификатор пользователя")
    username: str = Field(description="Отображаемое имя пользователя")
    email: EmailStr = Field(description="Адрес электронной почты")
    roles: list[str] = Field(description="Realm-роли Keycloak из токена сессии (user, vip_user, admin)")


class SubscriptionResponseDTO(BaseModel):
    """Ответ на запрос оформления подписки (имитация оплаты)."""

    message: str = Field(description="Текст подтверждения оформления подписки")
