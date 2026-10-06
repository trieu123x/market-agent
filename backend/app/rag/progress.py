"""Tiến độ ingest (parse → chunk → embed → save) để UI biết pipeline đang ở đâu và treo ở bước nào.

Worker là process riêng nên tiến độ được ghi vào cột `documents.ingest_progress` (JSONB):
một task nền ghi lại mỗi khi có thay đổi (tối đa 1 lần/giây) và ghi heartbeat định kỳ kể cả khi
không đổi, để UI phân biệt "bước đang chậm" với "worker đã chết".
"""
import asyncio
import contextlib
import copy
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update

from app.db.models import Document
from app.db.session import SessionLocal

log = logging.getLogger(__name__)

STEPS = ("parse", "chunk", "embed", "save")
FLUSH_INTERVAL = 1.0
HEARTBEAT_INTERVAL = 5.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_step() -> dict[str, Any]:
    return {
        "status": "pending",  # pending | running | done | failed
        "done": None,
        "total": None,
        "unit": None,
        "detail": None,
        "started_at": None,
        "finished_at": None,
        "progress_at": None,  # lần cuối done/detail thay đổi
    }


class IngestProgress:
    """Ghi nhận tiến độ từng bước. `advance` an toàn khi gọi từ thread parser (asyncio.to_thread)."""

    def __init__(self, document_id: uuid.UUID):
        self.document_id = document_id
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {
            "stage": None,
            "steps": {s: _empty_step() for s in STEPS},
            "heartbeat_at": None,
        }
        self._dirty = True
        self._task: asyncio.Task | None = None

    def _update(self, step: str, **fields: Any) -> None:
        with self._lock:
            self._state["steps"][step].update(fields)
            self._dirty = True

    def start(self, step: str, total: int | None = None, unit: str | None = None, detail: str | None = None) -> None:
        now = _now()
        done = 0 if total is not None else None
        with self._lock:
            self._state["stage"] = step
        self._update(
            step,
            status="running",
            done=done,
            total=total,
            unit=unit,
            detail=detail,
            started_at=now,
            progress_at=now,
        )

    def advance(self, step: str, done: int, total: int | None = None, detail: str | None = None) -> None:
        fields: dict[str, Any] = {"done": done, "progress_at": _now()}
        if total is not None:
            fields["total"] = total
        if detail is not None:
            fields["detail"] = detail
        self._update(step, **fields)

    def finish(self, step: str, done: int | None = None, total: int | None = None) -> None:
        now = _now()
        fields: dict[str, Any] = {"status": "done", "detail": None, "finished_at": now, "progress_at": now}
        if done is not None:
            fields["done"] = done
        if total is not None:
            fields["total"] = total
        self._update(step, **fields)

    def fail(self) -> None:
        """Đánh dấu bước đang chạy là failed (bước UI sẽ chỉ ra khi tài liệu FAILED)."""
        with self._lock:
            stage = self._state["stage"]
            if stage and self._state["steps"][stage]["status"] == "running":
                self._state["steps"][stage].update(status="failed", finished_at=_now())
                self._dirty = True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._state["heartbeat_at"] = _now()
            self._dirty = False
            return copy.deepcopy(self._state)

    async def flush(self) -> None:
        async with SessionLocal() as session:
            await session.execute(
                update(Document).where(Document.id == self.document_id).values(ingest_progress=self.snapshot())
            )
            await session.commit()

    async def _loop(self) -> None:
        loop = asyncio.get_running_loop()
        last = loop.time()
        while True:
            await asyncio.sleep(FLUSH_INTERVAL)
            if not self._dirty and loop.time() - last < HEARTBEAT_INTERVAL:
                continue
            try:
                await self.flush()
                last = loop.time()
            except Exception:
                log.warning("không ghi được tiến độ ingest của document %s", self.document_id, exc_info=True)

    def run_in_background(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Dừng task ghi nền (gọi trước transaction lưu cuối để không ghi đè trạng thái cuối)."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
