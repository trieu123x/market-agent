from fastapi import APIRouter, FastAPI

from app.api.v1 import auth
from app.core.config import get_settings
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title=get_settings().app_name)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
app.include_router(api_v1)


@app.get("/health")
async def health():
    return {"status": "ok"}
