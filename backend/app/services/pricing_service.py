from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ModelPricing


async def resolve_active_model(session: AsyncSession, model_id: str | None) -> ModelPricing | None:
    """Model được chọn (phải đang active) hoặc model mặc định nếu không truyền model_id."""
    stmt = select(ModelPricing).where(ModelPricing.is_system_active.is_(True))
    if model_id:
        stmt = stmt.where(ModelPricing.model_id == model_id)
    else:
        stmt = stmt.where(ModelPricing.is_default.is_(True))
    return await session.scalar(stmt.limit(1))
