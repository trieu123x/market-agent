import asyncio
import logging
import uuid
from pathlib import Path

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk, User
from app.db.session import SessionLocal
from app.guardrails import anti_ssrf
from app.rag import parsers
from app.rag.chunker import split_markdown
from app.rag.embedder import get_embedder

log = logging.getLogger(__name__)

EXTENSIONS = {".pdf": "PDF", ".docx": "DOCX", ".txt": "TXT"}


class InvalidUpload(ValueError):
    pass


def detect_file_type(filename: str, head: bytes) -> str:
    """Xác định loại file từ đuôi và magic bytes, lỗi nếu không hỗ trợ/không hợp lệ."""
    file_type = EXTENSIONS.get(Path(filename).suffix.lower())
    if file_type is None:
        raise InvalidUpload("Chỉ hỗ trợ PDF, DOCX, TXT")
    if file_type == "PDF" and not head.startswith(parsers.PDF_MAGIC):
        raise InvalidUpload("Nội dung không phải PDF hợp lệ")
    if file_type == "DOCX" and not head.startswith(parsers.ZIP_MAGIC):
        raise InvalidUpload("Nội dung không phải DOCX hợp lệ")
    return file_type


def _upload_dir() -> Path:
    """Thư mục lưu file upload (tạo nếu chưa có)."""
    path = Path(get_settings().upload_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


async def create_from_file(
    session: AsyncSession, user: User, scope: str, filename: str, data: bytes
) -> Document:
    """Lưu file upload và tạo bản ghi Document (PENDING)."""
    file_type = detect_file_type(filename, data[:8])
    doc_id = uuid.uuid4()
    path = _upload_dir() / f"{doc_id}{Path(filename).suffix.lower()}"
    await asyncio.to_thread(path.write_bytes, data)
    doc = Document(
        id=doc_id,
        user_id=user.id,
        scope=scope,
        title=Path(filename).name[:255],
        file_type=file_type,
        file_size_bytes=len(data),
        storage_path=str(path),
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc


async def create_from_url(session: AsyncSession, user: User, scope: str, url: str) -> Document:
    """Kiểm tra URL (anti-SSRF) và tạo bản ghi Document loại URL."""
    url = url.strip()
    await anti_ssrf.validate_url(url)
    doc = Document(user_id=user.id, scope=scope, title=url[:255], file_type="URL", storage_path=url)
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc


def visible_filter(user: User):
    """Điều kiện lọc tài liệu user được xem: SYSTEM hoặc của chính user."""
    return or_(Document.scope == "SYSTEM", Document.user_id == user.id)


async def list_visible(session: AsyncSession, user: User) -> list[Document]:
    """Liệt kê tài liệu user được xem, mới nhất trước."""
    stmt = select(Document).where(visible_filter(user)).order_by(Document.created_at.desc())
    return list((await session.scalars(stmt)).all())


async def get_visible(session: AsyncSession, user: User, document_id: uuid.UUID) -> Document | None:
    """Lấy một tài liệu nếu user có quyền xem, không thì None."""
    return await session.scalar(select(Document).where(Document.id == document_id, visible_filter(user)))


async def delete_document(session: AsyncSession, document_id: uuid.UUID) -> bool:
    """Xóa tài liệu (chunk xóa theo cascade) và file lưu trên đĩa."""
    doc = await session.get(Document, document_id)
    if doc is None:
        return False
    storage_path = doc.storage_path if doc.file_type != "URL" else None
    await session.delete(doc)  # chunks xóa theo ON DELETE CASCADE
    await session.commit()
    if storage_path:
        await asyncio.to_thread(Path(storage_path).unlink, missing_ok=True)
    return True


async def _load_content(doc: Document) -> str:
    """Đọc nội dung tài liệu (file hoặc tải URL) và chuyển thành Markdown."""
    s = get_settings()
    if doc.file_type == "URL":
        fetched = await anti_ssrf.safe_fetch(doc.storage_path, s.max_upload_bytes, s.url_fetch_timeout_seconds)
        doc.file_size_bytes = len(fetched.content)
        return await asyncio.to_thread(parsers.parse_to_markdown, "URL", fetched.content, fetched.content_type)
    data = await asyncio.to_thread(Path(doc.storage_path).read_bytes)
    return await asyncio.to_thread(parsers.parse_to_markdown, doc.file_type, data)


async def ingest(document_id: uuid.UUID) -> None:
    """Parse → Markdown → chunk → embed → lưu pgvector. Idempotent: chạy lại sẽ thay chunks cũ."""
    s = get_settings()
    async with SessionLocal() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            log.warning("ingest: document %s không tồn tại (có thể đã bị xóa)", document_id)
            return
        doc.processing_status = "PROCESSING"
        doc.error_message = None
        await session.commit()

        try:
            markdown = await _load_content(doc)
            chunks = await asyncio.to_thread(split_markdown, markdown, s.chunk_tokens, s.chunk_overlap_tokens)
            if not chunks:
                raise InvalidUpload("Không trích xuất được nội dung văn bản (file scan cần OCR?)")
            embedder = get_embedder()
            vectors = await embedder.embed_documents([c.content for c in chunks])

            await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
            session.add_all(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content=chunk.content,
                    metadata_={"headings": chunk.headings, "token_count": chunk.token_count, "embedding_model": embedder.name},
                    embedding=vector,
                )
                for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
            )
            doc.chunk_count = len(chunks)
            doc.processing_status = "READY"
            await session.commit()
            log.info("ingest: document %s READY với %d chunks", doc.id, len(chunks))
        except Exception as exc:
            log.exception("ingest: document %s FAILED", document_id)
            await session.rollback()
            doc = await session.get(Document, document_id)
            if doc is not None:
                doc.processing_status = "FAILED"
                doc.error_message = f"{type(exc).__name__}: {exc}"[:1000]
                await session.commit()
