"""Зависимости FastAPI для аутентификации и авторизации по ролям (RBAC)."""

from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import Depends, Header, HTTPException, status

from app.across_layers.entities.token_payload import TokenPayload
from app.across_layers.roles import ROLE_ADMIN, ROLE_VIP_USER
from app.application_layer.contracts.keycloak_protocol import (
    KeycloakClientProtocol,
    KeycloakInvalidTokenError,
)

_BEARER_PREFIX = "Bearer "

# Роли, которым разрешён доступ к чату: пользователь с подпиской и администратор
CHAT_ALLOWED_ROLES = frozenset({ROLE_VIP_USER, ROLE_ADMIN})

NO_SUBSCRIPTION_DETAIL = "У вас нет подписки. Доступ к чату запрещен."


# Depends-зависимости вне роутов DishkaRoute не обрабатывает — нужен явный inject
@inject
async def get_current_user(
    keycloak: FromDishka[KeycloakClientProtocol],
    authorization: Annotated[str | None, Header()] = None,
) -> TokenPayload:
    """Извлекает Bearer-токен из заголовка Authorization и валидирует его в Keycloak.

    Args:
        authorization: значение заголовка Authorization в формате `Bearer <token>`.

    Returns:
        Полезная нагрузка валидного JWT: идентификатор пользователя, email и роли.
    """
    if authorization is None or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется заголовок Authorization: Bearer <token>",
        )

    try:
        return await keycloak.validate_token(authorization[len(_BEARER_PREFIX):])
    except KeycloakInvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен недействителен или истёк",
        ) from e


# Аннотация для эндпоинтов: подставляет валидированный TokenPayload текущего пользователя
CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
