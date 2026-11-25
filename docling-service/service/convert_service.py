"""Сервис конвертации документов: вся работа с docling — здесь.

Слой не знает про HTTP: на вход — имя файла и байты, на выход —
готовый результат (filename/format/markdown) или ConversionError.
Коды ответов и тело ошибок решает контроллер.
"""

import logging
import tempfile
from pathlib import Path

from docling.document_converter import ConversionResult, DocumentConverter

logger = logging.getLogger(__name__)


class ConversionError(Exception):
    """Файл не удалось обработать: неподдерживаемый формат, битый файл
    или инфраструктурная проблема конвертера (нет весов моделей и т.п.)."""


class DoclingService:
    """Обёртка над DocumentConverter с кешированием пайплайна.

    Конвертер создаётся один раз и держит между запросами загруженные
    ML-модели (layout, таблицы, OCR) — пересоздавать его на каждый файл
    было бы расточительно.
    """

    def __init__(self) -> None:
        try:
            self._converter = DocumentConverter()
        except Exception as e:
            # Например, веса RapidOCR не залиты в DOCLING_ARTIFACTS_PATH —
            # отдаём доменной ошибкой, контроллер превратит её в HTTP 422.
            raise ConversionError(f"Конвертер не инициализирован: {e}") from e

    async def convert(self, filename: str | None, content: bytes) -> dict:
        """Конвертирует файл в Markdown.

        Формат определяется docling автоматически (PDF, DOCX, XLSX, PNG и др.).
        Для цифровых PDF OCR не запускается (текст извлекается напрямую),
        для изображений и сканов используется лёгкий CPU-OCR (RapidOCR).

        Args:
            filename: оригинальное имя файла; docling определяет формат
                по расширению, поэтому суффикс важен.
            content: сырые байты файла.

        Returns:
            Словарь {"filename", "format", "markdown"}.

        Raises:
            ConversionError: конвертация не удалась.
        """
        # docling определяет формат по расширению — сохраняем с оригинальным суффиксом
        suffix = Path(filename or "document.bin").suffix or ".bin"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            result: ConversionResult = self._converter.convert(tmp_path)
        except Exception as e:
            # Неподдерживаемый формат / битый файл — детали остаются в логе,
            # наружу уходит только доменная ошибка.
            logger.exception("Конвертация не удалась: %s", filename)
            raise ConversionError(str(e)) from e
        finally:
            tmp_path.unlink(missing_ok=True)

        document = result.document
        return {
            "filename": filename,
            "format": result.input.format.value,
            "markdown": document.export_to_markdown(),
        }


# --- Синглтон без сторонних библиотек -------------------------------------
# Экземпляр создаётся лениво, при первом обращении: конструктор поднимает
# пайплайн docling с весами моделей, что занимает секунды — незачем делать
# это на старте процесса, пока /health уже должен отвечать. Event loop
# FastAPI однопоточный, гонки при создании нет.

_service: DoclingService | None = None


def get_conversion_service() -> DoclingService:
    """Возвращает единственный экземпляр сервиса конвертации (лениво)."""
    global _service
    if _service is None:
        _service = DoclingService()
    return _service
