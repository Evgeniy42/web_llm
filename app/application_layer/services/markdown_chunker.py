import asyncio
import logging
import re
from dataclasses import dataclass

from app.application_layer.contracts.service_contracts.tokenizer_protocol import TokenizerProtocol

logger = logging.getLogger(__name__)

# Конец предложения: . ! ? … (возможно с закрывающей кавычкой/скобкой), за которым
# идёт пробельный символ. Используется, чтобы резать overlap-хвост не посреди
# предложения, а на его границе.
_SENTENCE_END_RE = re.compile(r"""[.!?…]+["»”')\]]?\s""")

# Максимум попыток ужать перекрытие, если чанк с ним не влезает в max_tokens
_OVERLAP_SHRINK_ATTEMPTS = 4


@dataclass
class _Block:
    """Структурный блок Markdown в токенном пространстве.

    Блок — неделимая единица сборки чанка: заголовок, абзац или целиком
    кодовый блок (внутри ``` ... ``` пустые строки не разрывают блок).
    text и tokens — одно и то же содержимое в двух представлениях:
    сборка идёт по токенам, итоговый чанк отдаётся текстом.
    """

    text: str
    tokens: list[int]
    is_heading: bool


class MarkdownChunker:
    """Нарезает Markdown документа на чанки для векторизации (этап 4).

    Стратегия — резка по структуре документа, а не по фиксированному
    окну символов:

    1. Markdown делится на блоки: каждый заголовок и каждый абзац —
       отдельный блок; кодовые блоки (``` ... ```) не разрываются
       даже если внутри них есть пустые строки.
    2. Блоки жадно собираются в чанки до max_tokens: граница чанка
       проходит только между блоками, поэтому чанк никогда не начинается
       посреди абзаца. min_tokens — цель, а не гарантия: короткий раздел
       (заголовок + абзац) собирается в маленький чанк, а не растягивается
       чужим текстом — жадная сборка сама сливает соседние блоки, пока
       они влезают в max_tokens.
    3. Блок длиннее max_tokens режется жёстко: сначала по предложениям,
       а отдельное предложение длиннее max_tokens — скользящим окном
       по токенам с тем же перекрытием.
    4. Соседние чанки перекрываются на overlap_ratio (10–15%) токенов
       предыдущего чанка: хвост предыдущего чанка обрезается по границе
       предложения и ставится перед текстом следующего; если чанк
       с перекрытием не влезает в max_tokens, перекрытие ужимается
       вдвое, вплоть до нуля.

    Счёт токенов — настоящий токенайзер модели (TokenizerProtocol,
    эндпоинты /tokenize и /detokenize llama-server): ограничения чанка
    считаются в том же токенном пространстве, в котором эмбеддинг-модель
    читает текст. Класс не хранит состояния и потокобезопасен.
    """

    def __init__(
        self,
        min_tokens: int = 300,
        max_tokens: int = 800,
        overlap_ratio: float = 0.12,
    ) -> None:
        if min_tokens <= 0:
            raise ValueError("min_tokens должен быть положительным")
        if max_tokens <= 0:
            raise ValueError("max_tokens должен быть положительным")
        if not 0 < overlap_ratio <= 0.5:
            raise ValueError("overlap_ratio должен быть в (0, 0.5]")
        self._min = min_tokens
        self._max = max_tokens
        self._overlap = overlap_ratio

    async def split(self, markdown: str, tokenizer: TokenizerProtocol) -> list[str]:
        """Нарезает Markdown на чанки-тексты (в порядке следования в документе).

        Args:
            markdown: Markdown документа (из docling).
            tokenizer: токенайзер модели для подсчёта токенов.

        Returns:
            Список текстов чанков; минимум один элемент.

        Raises:
            ValueError: markdown пуст или состоит из пробелов.
        """
        if not markdown.strip():
            raise ValueError("Нечего нарезать: markdown пуст")

        text_blocks = self._split_blocks(markdown)
        token_blocks = await self._tokenize_blocks(text_blocks, tokenizer)
        groups = await self._group_blocks(token_blocks, tokenizer)
        return await self._apply_overlap(groups, tokenizer)

    # --- Этап 1: Markdown -> структурные блоки (текст) ---

    def _split_blocks(self, markdown: str) -> list[tuple[str, bool]]:
        """Делит Markdown на блоки (текст, is_heading).

        Пустые строки разделяют абзацы; блок ``` ... ``` — атомарен
        (пустые строки внутри него абзац не завершают). Заголовок —
        блок, первая строка которого начинается с '#'.
        """
        blocks: list[tuple[str, bool]] = []
        paragraph: list[str] = []
        fence: list[str] | None = None

        def flush_paragraph() -> None:
            if not paragraph:
                return
            text = "\n".join(paragraph).strip()
            if text:
                blocks.append((text, paragraph[0].lstrip().startswith("#")))
            paragraph.clear()

        for line in markdown.splitlines():
            if fence is not None:
                fence.append(line)
                if line.strip().startswith("```"):
                    blocks.append(("\n".join(fence), False))
                    fence = None
            elif line.strip().startswith("```"):
                flush_paragraph()
                fence = [line]
            elif not line.strip():
                flush_paragraph()
            else:
                paragraph.append(line)
        flush_paragraph()
        if fence is not None:
            # Незакрытый кодовый блок: отдаём как обычный блок, не роняя документ
            blocks.append(("\n".join(fence), False))
        return blocks

    # --- Этап 2: блоки -> токены (пакетно, параллельно) ---

    async def _tokenize_blocks(self, text_blocks: list[tuple[str, bool]], tokenizer: TokenizerProtocol) -> list[_Block]:
        token_lists = await asyncio.gather(*(tokenizer.tokenize(text) for text, _ in text_blocks))
        return [
            _Block(text=text, tokens=tokens, is_heading=is_heading)
            for (text, is_heading), tokens in zip(text_blocks, token_lists, strict=True)
        ]

    # --- Этап 3: жадная сборка блоков в чанки ---

    async def _group_blocks(self, blocks: list[_Block], tokenizer: TokenizerProtocol) -> list[list[_Block]]:
        """Жадно собирает блоки в группы до max_tokens (резка — между блоками)."""
        groups: list[list[_Block]] = []
        current: list[_Block] = []
        current_len = 0

        for block in blocks:
            block_len = len(block.tokens)
            if block_len > self._max:
                if current:
                    groups.append(current)
                    current = []
                groups.extend(await self._hard_split(block, tokenizer))
            elif current and current_len + block_len > self._max:
                groups.append(current)
                current = [block]
                current_len = block_len
            else:
                current.append(block)
                current_len += block_len
        if current:
            groups.append(current)
        return groups

    async def _hard_split(self, block: _Block, tokenizer: TokenizerProtocol) -> list[list[_Block]]:
        """Жёстко режет блок длиннее max_tokens: по предложениям, затем окном.

        Без этого шага один гигантский абзац (например, таблица, которую
        docling отдал строкой) съел бы всю страницу контекста эмбеддинга.
        """
        sentences = [s for s in re.split(r"(?<=[.!?…])\s+", block.text) if s]
        if len(sentences) < 2:
            return self._window_split(block.tokens)

        token_lists = await asyncio.gather(*(tokenizer.tokenize(s) for s in sentences))
        groups: list[list[_Block]] = []
        current: list[_Block] = []
        current_len = 0
        for text, tokens in zip(sentences, token_lists, strict=True):
            part = _Block(text=text, tokens=tokens, is_heading=False)
            if len(tokens) > self._max:
                if current:
                    groups.append(current)
                    current = []
                # Предложение само длиннее max_tokens — только окно
                groups.extend(self._window_split(tokens))
            elif current and current_len + len(tokens) > self._max:
                groups.append(current)
                current = [part]
                current_len = len(tokens)
            else:
                current.append(part)
                current_len += len(tokens)
        if current:
            groups.append(current)
        return groups

    def _window_split(self, tokens: list[int]) -> list[list[_Block]]:
        """Режет длинный фрагмент скользящим окном по токенам.

        Шаг окна = max - overlap, чтобы куски тоже перекрывались; тексты
        окон декодируются из исходных токенов — границы по токенам точные,
        даже если окно режет слово посередине (для эмбеддинга это безвредно).
        """
        step = max(1, self._max - self._overlap_tokens(self._max))
        windows = [tokens[i : i + self._max] for i in range(0, len(tokens), step)]
        # Хвост короче overlap обычно почти полностью покрыт предпоследним окном
        if len(windows) >= 2 and len(windows[-1]) <= step:
            windows.pop()
        return [[_Block(text="", tokens=w, is_heading=False)] for w in windows]

    def _overlap_tokens(self, chunk_len: int) -> int:
        """Перекрытие в токенах для чанка длины chunk_len (с разумными пределами)."""
        return max(1, min(round(chunk_len * self._overlap), chunk_len // 2))

    # --- Этап 4: перекрытие соседних чанков и финальный текст ---

    async def _apply_overlap(self, groups: list[list[_Block]], tokenizer: TokenizerProtocol) -> list[str]:
        """Собирает группы блоков в тексты и добавляет перекрытие соседним чанкам."""
        texts: list[str] = []
        for group in groups:
            text = "\n\n".join(block.text for block in group if block.text)
            texts.append(text if text else await tokenizer.detokenize(group[0].tokens))

        if len(texts) < 2:
            return texts

        # Длины чанков в токенах нужны для расчёта перекрытия; считаем пакетно
        token_lists = await asyncio.gather(*(tokenizer.tokenize(t) for t in texts))

        result = [texts[0]]
        result_tokens = token_lists[0]
        for text in texts[1:]:
            overlapped = await self._with_overlap(result_tokens, text, tokenizer)
            result.append(overlapped)
            result_tokens = await tokenizer.tokenize(overlapped)
        return result

    async def _with_overlap(self, prev_tokens: list[int], text: str, tokenizer: TokenizerProtocol) -> str:
        """Ставит перед текстом хвост предыдущего чанка, ужимая его при переполнении."""
        k = self._overlap_tokens(len(prev_tokens))
        for _ in range(_OVERLAP_SHRINK_ATTEMPTS):
            if k <= 0:
                return text
            tail = await tokenizer.detokenize(prev_tokens[-k:])
            tail = self._cut_at_sentence_boundary(tail)
            if not tail.strip():
                k //= 2
                continue
            candidate = tail + "\n\n" + text
            if len(await tokenizer.tokenize(candidate)) <= self._max:
                return candidate
            k //= 2
        logger.debug("Перекрытие не влезло в max_tokens, чанк записан без него")
        return text

    @staticmethod
    def _cut_at_sentence_boundary(tail: str) -> str:
        """Отрезает начало хвоста до последней границы предложения.

        Граница ищется как знак конца предложения (. ! ? …, возможно с
        закрывающей кавычкой/скобкой), за которым идёт пробел; хвост без
        такой границы возвращается как есть (перекрытие посередине
        предложения — приемлемый компромисс).
        """
        matches = list(_SENTENCE_END_RE.finditer(tail))
        return tail[matches[-1].end() :] if matches else tail
