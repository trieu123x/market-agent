import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm_factory import LLMConfigError, provider_for
from app.db.models import ModelPricing
from app.schemas.admin import PricingUpdate


class PricingError(Exception):
    """Yêu cầu cập nhật bảng giá không hợp lệ (status HTTP + thông báo)."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


async def resolve_active_model(session: AsyncSession, model_id: str | None) -> ModelPricing | None:
    """Model được chọn (phải đang active) hoặc model mặc định nếu không truyền model_id."""
    stmt = select(ModelPricing).where(ModelPricing.is_system_active.is_(True))
    if model_id:
        stmt = stmt.where(ModelPricing.model_id == model_id)
    else:
        stmt = stmt.where(ModelPricing.is_default.is_(True))
    return await session.scalar(stmt.limit(1))


async def list_pricing(session: AsyncSession) -> list[ModelPricing]:
    stmt = select(ModelPricing).order_by(ModelPricing.is_default.desc(), ModelPricing.provider, ModelPricing.model_id)
    return list(await session.scalars(stmt))


async def upsert_pricing(
    session: AsyncSession, model_id: str, body: PricingUpdate, admin_id: uuid.UUID
) -> tuple[ModelPricing, bool]:
    """Cập nhật (hoặc tạo) giá model. Luôn giữ đúng một model mặc định và model mặc định phải active.
    Trả (row, created)."""
    row = await session.scalar(select(ModelPricing).where(ModelPricing.model_id == model_id))
    created = row is None
    if created:
        if body.provider is None or body.input_price_per_1k is None or body.output_price_per_1k is None:
            raise PricingError(404, "Model chưa có; muốn tạo mới cần provider, input_price_per_1k, output_price_per_1k")
        try:
            inferred = provider_for(model_id)
        except LLMConfigError as e:
            raise PricingError(400, str(e))
        if inferred != body.provider:
            raise PricingError(400, f"model_id '{model_id}' thuộc provider '{inferred}', không phải '{body.provider}'")
        row = ModelPricing(model_id=model_id, provider=body.provider, is_system_active=True, is_default=False)
        session.add(row)
    elif body.provider is not None and body.provider != row.provider:
        raise PricingError(400, "Không đổi được provider của model đã có")

    if body.input_price_per_1k is not None:
        row.input_price_per_1k = body.input_price_per_1k
    if body.output_price_per_1k is not None:
        row.output_price_per_1k = body.output_price_per_1k
    if body.is_system_active is not None:
        row.is_system_active = body.is_system_active
    if body.is_default is not None:
        if not body.is_default and row.is_default:
            raise PricingError(400, "Không bỏ mặc định trực tiếp được; hãy đặt model khác làm mặc định")
        row.is_default = body.is_default
    if row.is_default and not row.is_system_active:
        raise PricingError(400, "Model mặc định phải đang active; hãy đặt model khác làm mặc định trước")
    row.updated_by = admin_id

    if row.is_default:
        await session.execute(
            update(ModelPricing).where(ModelPricing.model_id != model_id, ModelPricing.is_default).values(is_default=False)
        )
    await session.commit()
    await session.refresh(row)
    return row, created
