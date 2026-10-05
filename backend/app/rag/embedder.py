from functools import lru_cache
from typing import Protocol

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.db.models.document import EMBEDDING_DIM


class Embedder(Protocol):
    name: str

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class GeminiEmbedder:
    """Gemini embedding, cắt về EMBEDDING_DIM chiều (Matryoshka) để khớp cột vector(1536)."""

    MAX_BATCH = 100  # giới hạn của batchEmbedContents

    def __init__(self, api_key: str, model: str, batch_size: int):
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=5)),
        )
        self.name = model
        self.batch_size = min(batch_size, self.MAX_BATCH)

    async def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIM)
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            resp = await self.client.aio.models.embed_content(
                model=self.name, contents=texts[i : i + self.batch_size], config=config
            )
            vectors.extend(e.values for e in resp.embeddings)
        return vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts, "RETRIEVAL_DOCUMENT")

    async def embed_query(self, text: str) -> list[float]:
        [vector] = await self._embed([text], "RETRIEVAL_QUERY")
        return vector


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if not s.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY trống – cần để tạo embedding Gemini")
    return GeminiEmbedder(s.google_api_key, s.embedding_model, s.embedding_batch_size)
