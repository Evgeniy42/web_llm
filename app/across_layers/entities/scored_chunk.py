from dataclasses import dataclass

from app.across_layers.entities.chunk_entity import ChunkEntity


@dataclass(frozen=True)
class ScoredChunk:
    """Чанк, найденный векторным поиском, вместе с оценкой релевантности.

    Результат поиска по коллекции Qdrant (этап 5): чанк вместе с метаданными
    (payload) и близостью к запросу. Score — косинусная близость (метрика
    коллекции), чем выше, тем ближе чанк к запросу.
    """

    chunk: ChunkEntity
    # Косинусная близость запроса и чанка (score точки Qdrant).
    score: float
