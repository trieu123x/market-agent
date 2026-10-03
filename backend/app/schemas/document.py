import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    title: str
    file_type: str
    file_size_bytes: int | None
    scope: str
    status: str
    message: str = "File đã được tiếp nhận và đang trích xuất nội dung ngầm."


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    scope: str
    title: str
    file_type: str
    file_size_bytes: int | None
    processing_status: str
    error_message: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=15)


class ChunkHit(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    chunk_index: int
    content: str
    metadata: dict
    score: float
    ranks: dict[str, int]


class SearchResponse(BaseModel):
    query: str
    results: list[ChunkHit]
