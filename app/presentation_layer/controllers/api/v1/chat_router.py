from dishka.integrations.fastapi import FromDishka, DishkaRoute
from fastapi import APIRouter, status

from app.application_layer.services.chat_service import ChatService
from app.presentation_layer.dto.chat_dto import ChatRequestDTO, ChatResponseDTO

router = APIRouter(
    tags=["chat"],
    route_class=DishkaRoute,
)


@router.post("/send", response_model=ChatResponseDTO, status_code=status.HTTP_200_OK)
async def send_message(request: ChatRequestDTO, service: FromDishka[ChatService]):
    """Отправляет сообщение в чат и возвращает ответ модели.

    Args:
        request: сообщение пользователя.

    Returns:
        Сгенерированный ответ чата.
    """
    response_text = await service.send_message(request.message)
    return ChatResponseDTO(response=response_text)
