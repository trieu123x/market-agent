"""Seed admin mặc định + bảng giá model. Chạy lại nhiều lần vẫn an toàn."""
import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import ModelPricing, User
from app.db.session import SessionLocal, engine

# (provider, model_id, input $/1k, output $/1k, is_default) — giá tham chiếu, chỉnh qua Admin API
PRICING = [
    ("openai", "gpt-4o", "0.002500", "0.010000", True),
    ("openai", "gpt-4o-mini", "0.000150", "0.000600", False),
    ("anthropic", "claude-sonnet-4-5", "0.003000", "0.015000", False),
    ("anthropic", "claude-haiku-4-5", "0.001000", "0.005000", False),
    ("google", "gemini-2.5-flash", "0.000300", "0.002500", False),
    ("google", "gemini-2.5-pro", "0.001250", "0.010000", False),
]


async def main() -> None:
    s = get_settings()
    async with SessionLocal() as session:
        admin = await session.scalar(select(User).where(User.email == s.admin_email.lower()))
        if admin is None:
            admin = User(
                email=s.admin_email.lower(),
                hashed_password=hash_password(s.admin_password),
                full_name="Admin",
                role="ADMIN",
            )
            session.add(admin)
            await session.flush()
            print(f"created admin {admin.email}")

        for provider, model_id, pin, pout, is_default in PRICING:
            exists = await session.scalar(select(ModelPricing).where(ModelPricing.model_id == model_id))
            if exists is None:
                session.add(
                    ModelPricing(
                        provider=provider,
                        model_id=model_id,
                        input_price_per_1k=pin,
                        output_price_per_1k=pout,
                        is_default=is_default,
                        updated_by=admin.id,
                    )
                )
                print(f"added pricing {model_id}")
        await session.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
