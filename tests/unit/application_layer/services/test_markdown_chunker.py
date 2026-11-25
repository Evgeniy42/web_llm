"""Юнит-тесты MarkdownChunker (этап 4): структурная нарезка чанков.

Вместо настоящего токенайзера модели — детерминированный фейк:
1 токен = 1 слово. Это не проверяет точность счёта токенов (её даёт
интеграционный тест с llama-server), но полностью проверяет логику
сборки чанков: границы блоков, жёсткий сплит, перекрытие, слияние хвоста.
"""

from itertools import pairwise

import pytest

from app.application_layer.services.markdown_chunker import MarkdownChunker


class FakeTokenizer:
    """Детерминированный токенайзер: слово = один токен (int id).

    detokenize строго обратен tokenize: словарь строится инкрементально,
    поэтому хвост предыдущего чанка восстанавливается пословно.
    """

    def __init__(self) -> None:
        self._vocab: dict[str, int] = {}
        self._words: list[str] = []

    async def tokenize(self, text: str) -> list[int]:
        return [self._id(w) for w in text.split()]

    async def detokenize(self, tokens: list[int]) -> str:
        return " ".join(self._words[i] for i in tokens)

    def count(self, text: str) -> int:
        return len(text.split())

    def _id(self, word: str) -> int:
        if word not in self._vocab:
            self._vocab[word] = len(self._words)
            self._words.append(word)
        return self._vocab[word]


def paragraph(n_words: int, prefix: str, end: str = "") -> str:
    """Абзац из n_words уникальных слов с опциональной концовкой-предложением."""
    return " ".join(f"{prefix}{i}" for i in range(n_words)) + end


@pytest.fixture
def tokenizer() -> FakeTokenizer:
    return FakeTokenizer()


@pytest.fixture
def chunker() -> MarkdownChunker:
    return MarkdownChunker(min_tokens=20, max_tokens=50, overlap_ratio=0.1)


class TestSplitBlocksAndGrouping:
    async def test_short_document_stays_single_chunk(self, chunker, tokenizer):
        markdown = paragraph(10, "w", end=".")
        chunks = await chunker.split(markdown, tokenizer)

        assert len(chunks) == 1
        assert chunks[0] == markdown

    async def test_document_split_into_multiple_chunks_under_max(self, chunker, tokenizer):
        # 10 абзацев по 30 токенов: в чанк max 50 влезает только один абзац
        markdown = "\n\n".join(paragraph(30, f"p{i}_") for i in range(10))
        chunks = await chunker.split(markdown, tokenizer)

        assert len(chunks) > 1
        assert all(tokenizer.count(c) <= 50 for c in chunks)

    async def test_paragraph_never_split_between_chunks(self, chunker, tokenizer):
        # Каждый абзац обязан целиком оказаться ровно в одном чанке
        paragraphs = [paragraph(30, f"p{i}_", end=".") for i in range(8)]
        chunks = await chunker.split("\n\n".join(paragraphs), tokenizer)

        for para in paragraphs:
            containing = [c for c in chunks if para in c]
            assert len(containing) == 1, f"абзац {para[:20]}... не в ровно одном чанке"

    async def test_blocks_merge_up_to_max(self, tokenizer):
        # 20 абзацев по 24 токена: max 50 -> два абзаца в чанк (48 <= 50)
        chunker = MarkdownChunker(min_tokens=20, max_tokens=50, overlap_ratio=0.1)
        paragraphs = [paragraph(24, f"p{i}_", end=".") for i in range(20)]
        chunks = await chunker.split("\n\n".join(paragraphs), tokenizer)

        assert len(chunks) == 10
        # 24 + 24 влезают, а 24*3 — нет: проверяем, что сборка жадная до предела
        assert all(30 < tokenizer.count(c) <= 50 + 50 * 0.1 for c in chunks)

    async def test_heading_travels_with_following_paragraph(self, chunker, tokenizer):
        markdown = "# Заголовок раздела\n\n" + paragraph(25, "w", end=".")
        chunks = await chunker.split(markdown, tokenizer)

        assert len(chunks) == 1
        assert chunks[0].startswith("# Заголовок раздела")

    async def test_greedy_fill_takes_exact_fit(self, tokenizer):
        chunker = MarkdownChunker(min_tokens=20, max_tokens=50, overlap_ratio=0.1)
        # 39 + 10 токенов: ровно 49 — соседние абзацы должны оказаться в одном чанке
        paragraphs = [paragraph(39, "a", end="."), paragraph(10, "b", end=".")]
        chunks = await chunker.split("\n\n".join(paragraphs), tokenizer)

        assert len(chunks) == 1
        assert "a0" in chunks[0] and "b0" in chunks[0]

    async def test_tiny_tail_stays_separate_when_no_room(self, tokenizer):
        chunker = MarkdownChunker(min_tokens=20, max_tokens=50, overlap_ratio=0.1)
        # 40 + 41 + 10: у чанка [b] нет места на хвост (41+10 > 50) — хвост остаётся отдельным
        paragraphs = [paragraph(40, "a", end="."), paragraph(41, "b", end="."), paragraph(10, "c", end=".")]
        chunks = await chunker.split("\n\n".join(paragraphs), tokenizer)

        assert len(chunks) == 3
        assert "c0" in chunks[2]

    async def test_code_fence_with_blank_lines_stays_intact(self, chunker, tokenizer):
        fence = "```python\nx = 1\n\ny = 2\n\nz = 3\n```"
        markdown = paragraph(10, "intro", end=".") + "\n\n" + fence
        chunks = await chunker.split(markdown, tokenizer)

        fence_block = next(c for c in chunks if "```" in c)
        assert "\n\n" in fence_block  # пустые строки внутри fence сохранились
        assert "y = 2" in fence_block


class TestHardSplit:
    async def test_oversized_paragraph_split_by_sentences(self, tokenizer):
        chunker = MarkdownChunker(min_tokens=20, max_tokens=50, overlap_ratio=0.1)
        # 6 предложений по 25 слов = 150 токенов в одном абзаце
        sentences = " ".join(paragraph(25, f"s{i}_", end=".") for i in range(6))
        chunks = await chunker.split(sentences, tokenizer)

        assert len(chunks) == 3
        assert all(tokenizer.count(c) <= 50 + 50 * 0.1 for c in chunks)

    async def test_paragraph_without_punctuation_split_by_window(self, tokenizer):
        chunker = MarkdownChunker(min_tokens=20, max_tokens=50, overlap_ratio=0.1)
        chunks = await chunker.split(paragraph(120, "w"), tokenizer)

        assert len(chunks) >= 2
        assert all(tokenizer.count(c) <= 50 for c in chunks)


class TestOverlap:
    async def test_chunks_overlap_with_previous_tail(self, chunker, tokenizer):
        # Чанки по одному абзацу (39 токенов); overlap ~ 10% = 4 токена хвоста
        paragraphs = [paragraph(38, f"p{i}_", end=" Конец.") for i in range(5)]
        chunks = await chunker.split("\n\n".join(paragraphs), tokenizer)

        assert len(chunks) == 5
        for prev, cur in pairwise(chunks):
            prev_tail = set(prev.split()[-4:])
            cur_head = set(cur.split()[:8])
            assert prev_tail & cur_head, f"нет перекрытия между чанками: {prev[-30:]!r} / {cur[:30]!r}"

    async def test_single_chunk_has_no_overlap(self, chunker, tokenizer):
        chunks = await chunker.split(paragraph(30, "w", end="."), tokenizer)
        assert len(chunks) == 1


class TestValidation:
    async def test_empty_markdown_rejected(self, chunker, tokenizer):
        with pytest.raises(ValueError, match="пуст"):
            await chunker.split("   \n\n  ", tokenizer)

    def test_invalid_params_rejected(self):
        with pytest.raises(ValueError):
            MarkdownChunker(min_tokens=0, max_tokens=50)
        with pytest.raises(ValueError):
            MarkdownChunker(min_tokens=10, max_tokens=0)
        with pytest.raises(ValueError):
            MarkdownChunker(min_tokens=10, max_tokens=50, overlap_ratio=0.6)
