"""Markdown splitter theo token: gom đoạn/câu thành chunk ≤ chunk_tokens, overlap ~overlap_tokens.

Ưu tiên cắt tại ranh giới đoạn (dòng trống), rồi tới câu, cuối cùng mới cắt cứng theo token.
"""
import re
from dataclasses import dataclass
from functools import lru_cache

import tiktoken

_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+|\n")


@dataclass
class Chunk:
    content: str
    heading: str | None
    token_count: int


@dataclass
class _Unit:
    text: str
    tokens: int
    heading: str | None


@lru_cache
def _encoding() -> tiktoken.Encoding:
    # Cùng tokenizer với text-embedding-3-*.
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoding().encode(text, disallowed_special=()))


def _token_windows(text: str, size: int) -> list[str]:
    enc = _encoding()
    ids = enc.encode(text, disallowed_special=())
    return [
        enc.decode_bytes(ids[i : i + size]).decode("utf-8", errors="ignore").strip()
        for i in range(0, len(ids), size)
    ]


def _units(text: str, chunk_tokens: int) -> list[_Unit]:
    units: list[_Unit] = []
    heading: str | None = None
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        if block.startswith("#"):
            heading = block.splitlines()[0].lstrip("#").strip() or heading
        n = count_tokens(block)
        if n <= chunk_tokens:
            units.append(_Unit(block, n, heading))
            continue
        for sentence in _SENTENCE_RE.split(block):
            sentence = sentence.strip()
            if not sentence:
                continue
            n = count_tokens(sentence)
            if n <= chunk_tokens:
                units.append(_Unit(sentence, n, heading))
            else:
                units.extend(_Unit(w, count_tokens(w), heading) for w in _token_windows(sentence, chunk_tokens) if w)
    return units


def _overlap_tail(units: list[_Unit], overlap_tokens: int) -> list[_Unit]:
    tail: list[_Unit] = []
    total = 0
    for u in reversed(units):
        if total + u.tokens > overlap_tokens:
            break
        tail.insert(0, u)
        total += u.tokens
    if not tail and units and overlap_tokens > 0:
        # Unit cuối quá dài để overlap nguyên vẹn → lấy phần đuôi theo token.
        last = units[-1]
        enc = _encoding()
        ids = enc.encode(last.text, disallowed_special=())[-overlap_tokens:]
        text = enc.decode_bytes(ids).decode("utf-8", errors="ignore").strip()
        if text:
            tail = [_Unit(text, len(ids), last.heading)]
    return tail


def _make_chunk(units: list[_Unit]) -> Chunk:
    content = "\n\n".join(u.text for u in units)
    return Chunk(content=content, heading=units[0].heading, token_count=count_tokens(content))


def split_markdown(text: str, chunk_tokens: int = 800, overlap_tokens: int = 150) -> list[Chunk]:
    if overlap_tokens >= chunk_tokens:
        raise ValueError("overlap_tokens phải nhỏ hơn chunk_tokens")
    chunks: list[Chunk] = []
    current: list[_Unit] = []
    current_tokens = 0
    for unit in _units(text, chunk_tokens):
        if current and current_tokens + unit.tokens > chunk_tokens:
            chunks.append(_make_chunk(current))
            current = _overlap_tail(current, overlap_tokens)
            current_tokens = sum(u.tokens for u in current)
            if current_tokens + unit.tokens > chunk_tokens:
                current, current_tokens = [], 0
        current.append(unit)
        current_tokens += unit.tokens
    if current:
        chunks.append(_make_chunk(current))
    return chunks
