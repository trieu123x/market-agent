import uuid
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, read_upload
from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_session
from app.guardrails.anti_ssrf import UnsafeURLError
from app.rag.retriever import retrieve
from app.schemas.document import (
    ChunkHit,
    DocumentChunkPage,
    DocumentOut,
    DocumentUploadResponse,
    SearchRequest,
    SearchResponse,
)
from app.services import document_service
from app.workers.tasks import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    scope: Literal["PRIVATE", "SYSTEM"] = Form(default="PRIVATE"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Nhận file hoặc URL, lưu tài liệu rồi đẩy task ingest nền (trả 202)."""
    if (file is None) == (not url):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cần gửi đúng một trong hai: file hoặc url")
    if scope == "SYSTEM" and user.role != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Chỉ ADMIN được upload tài liệu SYSTEM")

    if file is not None:
        data = await read_upload(file, get_settings().max_upload_bytes)
        try:
            doc = await document_service.create_from_file(session, user, scope, file.filename or "upload", data)
        except document_service.InvalidUpload as e:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(e))
    else:
        try:
            doc = await document_service.create_from_url(session, user, scope, url)
        except UnsafeURLError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"URL không hợp lệ: {e}")

    await ingest_document.kiq(str(doc.id))
    return DocumentUploadResponse(
        document_id=doc.id,
        title=doc.title,
        file_type=doc.file_type,
        file_size_bytes=doc.file_size_bytes,
        scope=doc.scope,
        status=doc.processing_status,
    )


@router.get("", response_model=list[DocumentOut])
async def list_documents(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    """Liệt kê tài liệu user được xem."""
    return await document_service.list_visible(session, user)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    """Xem chi tiết một tài liệu (404 nếu không có quyền)."""
    doc = await document_service.get_visible(session, user, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


@router.get("/{document_id}/chunks", response_model=DocumentChunkPage)
async def list_chunks(
    document_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Các chunk đã lưu của một tài liệu, theo thứ tự (404 nếu không có quyền xem tài liệu)."""
    if await document_service.get_visible(session, user, document_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    total, chunks = await document_service.list_chunks(session, document_id, offset, limit)
    return DocumentChunkPage(total=total, offset=offset, items=chunks)


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    """Debug/kiểm thử retriever: hybrid RRF (top 15) → reranker → top_k."""
    hits = await retrieve(session, body.query, user.id, body.top_k)
    return SearchResponse(query=body.query, results=[ChunkHit(**asdict(h)) for h in hits])
