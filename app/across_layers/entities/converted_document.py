from dataclasses import dataclass


@dataclass(frozen=True)
class ConvertedDocument:
    """Результат конвертации документа микросервисом docling-service.

    Один входной файл -> один Markdown: docling сам определяет формат
    (PDF/DOCX/XLSX/PNG/...) и применяет нужный пайплайн. Формат отдаём
    в метаданных — пригодится для отладки и фильтров на этапе 4.
    """

    filename: str
    format: str
    markdown: str
