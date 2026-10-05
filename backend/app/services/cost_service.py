"""Cost auditor: ghi llm_cost_logs cho từng lần gọi LLM và tổng hợp báo cáo chi phí."""
import logging
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LLMCostLog, ModelPricing
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

_MICRO_USD = Decimal("0.000001")


@dataclass
class UsageRecord:
    node: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal
    pricing_missing: bool


def compute_cost(pricing: ModelPricing, prompt_tokens: int, completion_tokens: int) -> Decimal:
    cost = (prompt_tokens * pricing.input_price_per_1k + completion_tokens * pricing.output_price_per_1k) / 1000
    return cost.quantize(_MICRO_USD, rounding=ROUND_HALF_UP)


async def record_usage(
    user_id: uuid.UUID, thread_id: str, node: str, model_id: str, prompt_tokens: int, completion_tokens: int
) -> UsageRecord:
    """Ghi một dòng llm_cost_logs (session riêng: gọi từ trong stream SSE)."""
    async with SessionLocal() as session:
        pricing = await session.scalar(select(ModelPricing).where(ModelPricing.model_id == model_id))
        if pricing is None:
            # Vẫn ghi token để không mất dấu; chi phí 0 được đánh dấu rõ cho admin/UI
            logger.error("model_id '%s' không có trong model_pricing – cost_usd ghi 0", model_id)
            cost = Decimal(0)
        else:
            cost = compute_cost(pricing, prompt_tokens, completion_tokens)
        session.add(
            LLMCostLog(
                user_id=user_id,
                thread_id=thread_id,
                node_name=node,
                model_id=model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost_usd=cost,
            )
        )
        await session.commit()
    return UsageRecord(
        node, model_id, prompt_tokens, completion_tokens, prompt_tokens + completion_tokens, cost, pricing is None
    )


async def thread_totals(thread_id: str) -> tuple[int, Decimal]:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(
                    func.coalesce(func.sum(LLMCostLog.total_tokens), 0),
                    func.coalesce(func.sum(LLMCostLog.cost_usd), 0),
                ).where(LLMCostLog.thread_id == thread_id)
            )
        ).one()
    return int(row[0]), Decimal(row[1])


async def cost_report(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    user_id: uuid.UUID | None = None,
    model_id: str | None = None,
) -> dict:
    """Tổng token/chi phí + breakdown theo model, node, user. end_date tính trọn ngày."""
    filters = []
    if start_date:
        filters.append(LLMCostLog.created_at >= start_date)
    if end_date:
        filters.append(LLMCostLog.created_at < end_date + timedelta(days=1))
    if user_id:
        filters.append(LLMCostLog.user_id == user_id)
    if model_id:
        filters.append(LLMCostLog.model_id == model_id)

    tokens = func.coalesce(func.sum(LLMCostLog.total_tokens), 0)
    cost = func.coalesce(func.sum(LLMCostLog.cost_usd), 0)

    async def breakdown(column, key: str) -> list[dict]:
        stmt = select(column, tokens, cost).where(*filters).group_by(column).order_by(cost.desc())
        return [
            {key: str(k), "tokens": int(t), "cost_usd": float(c)} for k, t, c in (await session.execute(stmt)).all()
        ]

    total_tokens, total_cost = (await session.execute(select(tokens, cost).where(*filters))).one()
    return {
        "total_tokens_consumed": int(total_tokens),
        "total_cost_usd": float(total_cost),
        "breakdown_by_model": await breakdown(LLMCostLog.model_id, "model_id"),
        "breakdown_by_node": await breakdown(LLMCostLog.node_name, "node_name"),
        "breakdown_by_user": await breakdown(LLMCostLog.user_id, "user_id"),
    }
