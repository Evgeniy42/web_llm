from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Form, HTTPException, status

from app.across_layers.roles import ROLE_ADMIN
from app.application_layer.services.embedding_service import EmbeddingService
from app.presentation_layer.dependencies.auth import CurrentUser
from app.presentation_layer.dto.embedding_dto import (
    INGEST_SUCCESS_MESSAGE,
    IngestRequestDTO,
    IngestResponseDTO,
)

router = APIRouter(
    tags=["rag"],
    route_class=DishkaRoute,
)


@router.post("/embed", response_model=IngestResponseDTO, status_code=status.HTTP_200_OK)
async def ingest_document(
    form: Annotated[IngestRequestDTO, Form()],
    service: FromDishka[EmbeddingService],
    user: CurrentUser,
) -> IngestResponseDTO:
    """Загружает документ в векторное хранилище (только для администратора).

    Эндпоинт этапа 3 RAG: файл -> конвертация в Markdown (микросервис
    docling-service) -> эмбеддинг (llama-server, Qwen3-Embedding) -> точка
    в коллекции Qdrant. Проверка роли идёт ПЕРЕД любой обработкой файла:
    пользователь без роли admin получает 403, файл никуда не отправляется
    и в базу не записывается. Ошибки обработки (конвертация, эмбеддинги,
    Qdrant) превращает хэндлер в ответ с success=False.
    """
    if ROLE_ADMIN not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступно только администратору",
        )

    content = await form.file.read()
    doc_id, chunks_count, detected_format = await service.ingest_document(
        filename=form.file.filename or "document",
        content=content,
        doc_id=form.doc_id,
    )
    return IngestResponseDTO(
        success=True,
        message=INGEST_SUCCESS_MESSAGE,
        doc_id=doc_id,
        chunks_count=chunks_count,
        format=detected_format,
    )
