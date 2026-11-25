import logging

from fastapi import HTTPException, UploadFile
from fastapi.routing import APIRouter

from service.convert_service import ConversionError, get_conversion_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/convert")
async def convert(file: UploadFile) -> dict:
    """Конвертирует загруженный файл в Markdown (см. DoclingService.convert)."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Пустой файл")

    try:
        return await get_conversion_service().convert(file.filename, content)
    except ConversionError as e:
        raise HTTPException(status_code=422, detail=f"Не удалось обработать файл: {e}") from e
