from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

TextStr = Annotated[str, StringConstraints(min_length=1, max_length=10000)]


class EmbeddingRequestDTO(BaseModel):
    """Текст для векторизации (тестовый эндпоинт этапа 1)."""

    model_config = ConfigDict(extra="forbid")

    text: TextStr = Field(description="Текст для эмбеддинга, 1-10000 символов")


class EmbeddingResponseDTO(BaseModel):
    """Результат векторизации: сам вектор и сводка для самопроверки."""

    model_config = ConfigDict(from_attributes=True)

    dimensions: int = Field(description="Размерность вектора (ожидается 1024)")
    norm: float = Field(description="L2-норма вектора: ~1.0 подтверждает нормализацию")
    preview: list[float] = Field(description="Первые 8 координат вектора")
