import hashlib
import logging
import math
import re
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.db.models.document import EMBEDDING_DIM

log = logging.getLogger(__name__)


class Embedder(Protocol):
    name: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str, batch_size: int):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key)
        self.name = model
        self.batch_size = batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            resp = await self.client.embeddings.create(
                model=self.name, input=texts[i : i + self.batch_size], dimensions=EMBEDDING_DIM
            )
            vectors.extend(d.embedding for d in sorted(resp.data, key=lambda d: d.index))
        return vectors


class HashEmbedder:
    """Embedding giả lập offline (feature hashing trên từ). Chỉ dùng cho dev/test:
    bắt được trùng lặp từ vựng, không hiểu ngữ nghĩa."""

    name = "hash"

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * EMBEDDING_DIM
        for word in re.findall(r"\w+", text.lower()):
            h = int.from_bytes(hashlib.blake2b(word.encode(), digest_size=8).digest(), "big")
            vec[h % EMBEDDING_DIM] += 1.0 if (h >> 63) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            vec[0], norm = 1.0, 1.0  # tránh vector 0 (cosine distance = NaN)
        return [v / norm for v in vec]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    provider = s.embedding_provider
    if provider == "auto":
        provider = "openai" if s.openai_api_key else "hash"
        if provider == "hash":
            log.warning("OPENAI_API_KEY trống → dùng HashEmbedder (chỉ phù hợp dev/test)")
    if provider == "openai":
        if not s.openai_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=openai nhưng OPENAI_API_KEY trống")
        return OpenAIEmbedder(s.openai_api_key, s.embedding_model, s.embedding_batch_size)
    return HashEmbedder()
