from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.models import User
from app.db.session import get_session
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)):
    try:
        return await auth_service.register(session, body.email, body.password, body.full_name)
    except auth_service.EmailTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    user = await auth_service.authenticate(session, body.email, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    return TokenResponse(access_token=create_access_token(str(user.id), user.role))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(user: User = Depends(get_current_user)):
    """Đổi token còn hạn lấy token mới (sliding session); role lấy lại từ DB."""
    return TokenResponse(access_token=create_access_token(str(user.id), user.role))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
