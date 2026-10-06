import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import close_graph, get_graph
from app.api.v1 import admin, agent, auth, documents
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.rag import reranker
from app.workers.broker import broker

setup_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not broker.is_worker_process:
        await broker.startup()
    await get_graph()  # chạy migration checkpointer trước request đầu tiên (xem checkpointer.py)
    # Nạp Cross-Encoder ở nền (lần đầu phải tải model) để không chặn startup
    warmup = asyncio.create_task(reranker.warmup()) if get_settings().reranker_enabled else None
    yield
    if warmup:
        warmup.cancel()
    await close_graph()
    if not broker.is_worker_process:
        await broker.shutdown()


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Thread-Id"],
)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
api_v1.include_router(documents.router)
api_v1.include_router(agent.router)
api_v1.include_router(admin.router)
app.include_router(api_v1)


@app.get("/health")
async def health():
    return {"status": "ok"}
