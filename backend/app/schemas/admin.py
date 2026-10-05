import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserStatusResponse(BaseModel):
    user_id: uuid.UUID
    is_active: bool
    message: str = "User status updated successfully"


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime


class PricingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    model_id: str
    input_price_per_1k: float
    output_price_per_1k: float
    is_system_active: bool
    is_default: bool
    updated_at: datetime


class PricingUpdate(BaseModel):
    """Field bỏ trống = giữ nguyên. Model chưa có → tạo mới (bắt buộc provider + 2 đơn giá)."""

    provider: Literal["google", "openai", "anthropic"] | None = None
    input_price_per_1k: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=6)
    output_price_per_1k: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=6)
    is_system_active: bool | None = None
    is_default: bool | None = None


class CostBreakdownModel(BaseModel):
    model_id: str
    tokens: int
    cost_usd: float


class CostBreakdownNode(BaseModel):
    node_name: str
    tokens: int
    cost_usd: float


class CostBreakdownUser(BaseModel):
    user_id: uuid.UUID
    tokens: int
    cost_usd: float


class CostReport(BaseModel):
    total_tokens_consumed: int
    total_cost_usd: float
    breakdown_by_model: list[CostBreakdownModel]
    breakdown_by_node: list[CostBreakdownNode]
    breakdown_by_user: list[CostBreakdownUser]
