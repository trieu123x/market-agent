from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.db.models import User


class EmailTaken(Exception):
    pass


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email.lower()))


async def register(session: AsyncSession, email: str, password: str, full_name: str | None) -> User:
    if await get_by_email(session, email):
        raise EmailTaken(email)
    user = User(email=email.lower(), hashed_password=hash_password(password), full_name=full_name)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    user = await get_by_email(session, email)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user
