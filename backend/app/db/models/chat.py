import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # = LangGraph thread_id
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(String(255), server_default="Chiến dịch mới")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ThreadMessage(Base):
    __tablename__ = "thread_messages"
    __table_args__ = (
        CheckConstraint(
            "sender_role IN ('USER', 'ASSISTANT', 'SYSTEM', 'HUMAN_INTERRUPT')", name="ck_thread_messages_role"
        ),
        CheckConstraint(
            "content_type IN ('TEXT', 'OUTLINE_CARD', 'DRAFTS_CARD', 'FACT_CHECK_REPORT')",
            name="ck_thread_messages_content_type",
        ),
        Index("idx_thread_messages_thread", "thread_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    thread_id: Mapped[str] = mapped_column(String(100), ForeignKey("chat_threads.id", ondelete="CASCADE"))
    sender_role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(20), server_default="TEXT")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
