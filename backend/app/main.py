from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.agent.graph import close_graph, get_graph
from app.api.v1 import admin, agent, auth, documents
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.workers.broker import broker

setup_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not broker.is_worker_process:
        await broker.startup()
    await get_graph()  # chạy migration checkpointer trước request đầu tiên (xem checkpointer.py)
    yield
    await close_graph()
    if not broker.is_worker_process:
        await broker.shutdown()


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
api_v1.include_router(documents.router)
api_v1.include_router(agent.router)
api_v1.include_router(admin.router)
app.include_router(api_v1)


@app.get("/health")
async def health():
    return {"status": "ok"}
