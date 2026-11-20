import math

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, status

from app.application_layer.services.embedding_service import EmbeddingService
from app.presentation_layer.dto.embedding_dto import (
    EmbeddingRequestDTO,
    EmbeddingResponseDTO,
)

router = APIRouter(
    tags=["rag"],
    route_class=DishkaRoute,
)


@router.post("/embed", response_model=EmbeddingResponseDTO, status_code=status.HTTP_200_OK)
async def embed_text(request: EmbeddingRequestDTO, service: FromDishka[EmbeddingService]):
    """Векторизует текст через локальный embedding-сервис.

    Тестовый эндпоинт этапа 1 RAG: проверяет, что llama-server с
    Qwen3-Embedding поднят и отдаёт векторы ожидаемой размерности
    (1024) с L2-нормой ~1.0. Аутентификация на этапе 1 не требуется —
    эндпоинт внутренний, уберём/защитим после сборки пайплайна.
    """
    vector = await service.embed(request.text)
    return EmbeddingResponseDTO(
        dimensions=len(vector),
        norm=_l2_norm(vector),
        preview=vector[:8],
    )


def _l2_norm(vector: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))
