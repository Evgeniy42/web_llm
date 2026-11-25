from typing import Annotated

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

DocIdStr = Annotated[str, StringConstraints(min_length=1, max_length=128)]


# Стандартные сообщения итога загрузки: источник истины для ответа и хэндлеров
INGEST_SUCCESS_MESSAGE = "Файл успешно загрузился на сервер"
INGEST_ERROR_MESSAGE = "Произошла ошибка. Файл не был загружен в базу данных"


class IngestRequestDTO(BaseModel):
    """Multipart-форма загрузки документа: файл + опциональные поля.

    Файл объявлен полем модели — в FastAPI 0.115 смешение отдельного
    UploadFile-параметра и Form-модели не работает, а модель с файлом
    внутри парсится корректно.
    """

    model_config = ConfigDict(extra="forbid")

    file: UploadFile = Field(description="Файл документа любого поддерживаемого формата")
    doc_id: DocIdStr | None = Field(
        default=None,
        description="Идентификатор документа; по умолчанию — имя файла без расширения",
    )


class IngestResponseDTO(BaseModel):
    """Результат загрузки документа в векторное хранилище.

    При ошибке обработки (сервис конвертации, эмбеддинги, Qdrant) тело
    ответа всё равно это DTO: success=False и стандартное сообщение,
    детали — в логах сервера. См. хэндлеры в http_exception_handlers.

    Этап 4: документ нарезается на чанки, поэтому вместо одиночного
    point_id в ответе число записанных чанков (chunks_count). Точки
    чанков имеют детерминированные id: uuid5(doc_id, chunk_index).
    """

    model_config = ConfigDict(from_attributes=True)

    success: bool = Field(description="Успешна ли загрузка документа в базу")
    message: str = Field(description="Человекочитаемый итог загрузки")
    doc_id: str | None = Field(default=None, description="Идентификатор документа")
    chunks_count: int | None = Field(default=None, description="Число записанных чанков документа")
    format: str | None = Field(default=None, description="Определённый docling формат файла")
