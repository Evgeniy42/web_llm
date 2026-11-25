"""Зависимости FastAPI для аутентификации и авторизации по ролям (RBAC)."""

from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import Depends, Header, HTTPException, Request, status

from app.across_layers.entities.token_payload import TokenPayload
from app.across_layers.roles import ROLE_ADMIN, ROLE_VIP_USER
from app.application_layer.contracts.client_contracts.keycloak_protocol import (
    KeycloakClientProtocol,
    KeycloakInvalidTokenError,
)

_BEARER_PREFIX = "Bearer "

# Имена сессионных cookie, устанавливаемых backend'ом при входе (HttpOnly)
ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"

# Роли, которым разрешён доступ к чату: пользователь с подпиской и администратор
CHAT_ALLOWED_ROLES = frozenset({ROLE_VIP_USER, ROLE_ADMIN})

NO_SUBSCRIPTION_DETAIL = "У вас нет подписки. Доступ к чату запрещен."


# Depends-зависимости вне роутов DishkaRoute не обрабатывает — нужен явный inject
@inject
async def get_current_user(
    keycloak: FromDishka[KeycloakClientProtocol],
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> TokenPayload:
    """Извлекает токен сессии и валидирует его в Keycloak.

    Основной путь — HttpOnly-cookie access_token, установленная backend'ом
    при входе; заголовок Authorization: Bearer поддерживается для
    совместимости (и имеет приоритет, если передан).

    Args:
        authorization: значение заголовка Authorization в формате `Bearer <token>`.

    Returns:
        Полезная нагрузка валидного JWT: идентификатор пользователя, email и роли.
    """
    token: str | None = None
    if authorization is not None and authorization.startswith(_BEARER_PREFIX):
        token = authorization[len(_BEARER_PREFIX):]
    else:
        token = request.cookies.get(ACCESS_TOKEN_COOKIE)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется сессия: cookie access_token или заголовок Authorization: Bearer <token>",
        )

    try:
        return await keycloak.validate_token(token)
    except KeycloakInvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен недействителен или истёк",
        ) from e


# Аннотация для эндпоинтов: подставляет валидированный TokenPayload текущего пользователя
CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
