from app.across_layers.entities.scored_chunk import ScoredChunk

SYSTEM_PROMPT_TEMPLATE = """Ты — ассистент, который отвечает на вопросы пользователя,
опираясь на фрагменты загруженных документов.

Правила:
1. Отвечай, опираясь ТОЛЬКО на контекст ниже. Не используй общие знания, если ответ не следует из контекста.
2. Если в контексте нет информации для ответа, прямо скажи: «В загруженных документах нет информации по этому вопросу».
3. Указывай источник (имя документа), из которого взят ответ.
4. Отвечай на языке вопроса пользователя.

Контекст:
{context}"""

# Текст-заглушка, когда поиск не нашёл ни одного релевантного чанка:
# модель не должна выдумывать ответ из общих знаний.
NO_CONTEXT_PLACEHOLDER = "(релевантные фрагменты документов не найдены)"

# Формат одного фрагмента контекста: номер, источник и текст чанка.
_CHUNK_TEMPLATE = "[{number}] Источник: {source}\n{content}"


def build_context(chunks: list[ScoredChunk]) -> str:
    """Склеивает найденные чанки в блок контекста для системного промпта.

    Каждый чанк нумеруется и подписывается источником — модель может
    ссылаться на номер/источник в ответе. Пустой список -> заглушка,
    при которой промпт велит модели честно отказаться от ответа.
    """
    if not chunks:
        return NO_CONTEXT_PLACEHOLDER
    return "\n\n".join(
        _CHUNK_TEMPLATE.format(
            number=index,
            source=scored.chunk.source,
            content=scored.chunk.content.strip(),
        )
        for index, scored in enumerate(chunks, start=1)
    )


def build_system_prompt(chunks: list[ScoredChunk]) -> str:
    """Собирает системный промпт: шаблон + блок контекста из чанков."""
    return SYSTEM_PROMPT_TEMPLATE.format(context=build_context(chunks))
