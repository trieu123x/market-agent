import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelPricing(Base):
    __tablename__ = "model_pricing"
    __table_args__ = (
        CheckConstraint("provider IN ('google', 'openai', 'anthropic')", name="ck_model_pricing_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    provider: Mapped[str] = mapped_column(String(50))
    model_id: Mapped[str] = mapped_column(String(100), unique=True)
    input_price_per_1k: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    output_price_per_1k: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    is_system_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    is_default: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
