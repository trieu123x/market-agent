import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent.state import PLATFORMS
from app.services.attachment_service import MAX_ATTACHMENT_CHARS, MAX_ATTACHMENTS

ThreadId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")]


class ChatAttachment(BaseModel):
    """Nội dung đã trích từ /agent/attachments, client gửi kèm brief."""

    kind: Literal["image", "document"]
    filename: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=MAX_ATTACHMENT_CHARS + 50)  # + chỗ cho dấu "…" khi cắt
    truncated: bool = False


class AttachmentOut(ChatAttachment):
    mime_type: str
    size_bytes: int


class ChatStreamRequest(BaseModel):
    thread_id: ThreadId | None = None  # None → server tự sinh, trả về trong event status đầu tiên
    message: str = Field(min_length=1, max_length=8000)
    model_id: str | None = None  # None → model mặc định trong model_pricing
    attachments: list[ChatAttachment] = Field(default_factory=list, max_length=MAX_ATTACHMENTS)


class ChatResumeRequest(BaseModel):
    thread_id: ThreadId
    stage: Literal["OUTLINE_APPROVAL", "DRAFTS_APPROVAL"]
    action: Literal["APPROVE", "EDIT", "REJECT"]
    updated_outline: str | None = Field(default=None, max_length=20000)
    updated_drafts: dict[str, str] | None = None
    feedback: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _check_action(self):
        if self.action == "EDIT":
            if self.stage == "OUTLINE_APPROVAL" and not (self.updated_outline or "").strip():
                raise ValueError("EDIT dàn ý cần updated_outline")
            if self.stage == "DRAFTS_APPROVAL" and not self.updated_drafts:
                raise ValueError("EDIT bản thảo cần updated_drafts")
        if self.updated_drafts and not set(self.updated_drafts) <= set(PLATFORMS):
            raise ValueError(f"updated_drafts chỉ nhận các kênh {', '.join(PLATFORMS)}")
        if self.action == "REJECT" and self.stage == "DRAFTS_APPROVAL":
            raise ValueError("DRAFTS_APPROVAL chỉ hỗ trợ APPROVE hoặc EDIT")
        return self


class ModelOption(BaseModel):
    model_id: str
    provider: str
    is_default: bool
    available: bool  # provider đã cấu hình API key


class ThreadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class PendingInterrupt(BaseModel):
    stage: str
    message: str | None
    data: dict


class ThreadStateOut(BaseModel):
    thread_id: str
    pending: PendingInterrupt | None  # HITL đang chờ duyệt (None nếu không)
    total_tokens: int
    total_cost_usd: float


class ThreadMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    sender_role: str
    content: str
    content_type: str
    metadata: dict = Field(validation_alias="metadata_")
    created_at: datetime
