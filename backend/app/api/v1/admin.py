import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.models import User
from app.db.session import get_session
from app.schemas.admin import (
    AdminUserOut,
    CostReport,
    PricingOut,
    PricingUpdate,
    UserStatusResponse,
    UserStatusUpdate,
)
from app.services import cost_service, document_service, pricing_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(session: AsyncSession = Depends(get_session)):
    return list(await session.scalars(select(User).order_by(User.created_at.desc())))


@router.patch("/users/{user_id}/status", response_model=UserStatusResponse)
async def update_user_status(
    user_id: uuid.UUID,
    body: UserStatusUpdate,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Kích hoạt / vô hiệu hóa tài khoản (token cũ của user bị khóa cũng bị từ chối ngay, xem deps.py)."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id and not body.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Không thể tự vô hiệu hóa tài khoản của mình")
    user.is_active = body.is_active
    await session.commit()
    return UserStatusResponse(user_id=user.id, is_active=user.is_active)


@router.get("/pricing", response_model=list[PricingOut])
async def list_pricing(session: AsyncSession = Depends(get_session)):
    return await pricing_service.list_pricing(session)


@router.put("/pricing/{model_id}", response_model=PricingOut)
async def upsert_pricing(
    model_id: str,
    body: PricingUpdate,
    response: Response,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Cập nhật đơn giá / trạng thái / mặc định của model; model chưa có thì tạo mới (201)."""
    try:
        row, created = await pricing_service.upsert_pricing(session, model_id, body, admin.id)
    except pricing_service.PricingError as e:
        raise HTTPException(e.status_code, str(e))
    if created:
        response.status_code = status.HTTP_201_CREATED
    return row


@router.get("/analytics/costs", response_model=CostReport)
async def cost_analytics(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user_id: uuid.UUID | None = Query(default=None),
    model_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Tổng token + chi phí USD, breakdown theo model / node / user. end_date tính trọn ngày."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "start_date phải trước end_date")
    return await cost_service.cost_report(session, start_date, end_date, user_id, model_id)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    if not await document_service.delete_document(session, document_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
