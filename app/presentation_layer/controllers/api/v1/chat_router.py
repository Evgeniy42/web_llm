from dishka.integrations.fastapi import FromDishka, DishkaRoute
from fastapi import APIRouter, status

from app.application_layer.services.chat_service import ChatService
from app.presentation_layer.dependencies.auth import (
    CHAT_ALLOWED_ROLES,
    NO_SUBSCRIPTION_DETAIL,
    CurrentUser,
)
from app.presentation_layer.dto.chat_dto import ChatRequestDTO, ChatResponseDTO

router = APIRouter(
    tags=["chat"],
    route_class=DishkaRoute,
)


@router.post("/send", response_model=ChatResponseDTO, status_code=status.HTTP_200_OK)
async def send_message(request: ChatRequestDTO, service: FromDishka[ChatService], user: CurrentUser):
    """Отправляет сообщение в чат и возвращает ответ модели.

    Доступ по роли (RBAC): чат доступен пользователю с подпиской (vip_user)
    и администратору; роли читаются из JWT в заголовке Authorization.
    Пользователю без подписки отказ возвращается как обычное сообщение чата,
    чтобы фронтенд показал его в диалоге.

    Args:
        request: сообщение пользователя.
        user: полезная нагрузка валидированного JWT (роли Keycloak).

    Returns:
        Ответ чата: сгенерированный текст либо сообщение о запрете доступа.
        Без валидного токена — 401.
    """
    if not user.roles & CHAT_ALLOWED_ROLES:
        return ChatResponseDTO(response=NO_SUBSCRIPTION_DETAIL)

    response_text = await service.send_message(request.message)
    return ChatResponseDTO(response=response_text)
