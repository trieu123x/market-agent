"""Taskiq broker.

Chạy worker (khi TASK_BROKER=redis):
    taskiq worker app.workers.broker:broker app.workers.tasks
"""
from taskiq import AsyncBroker, InMemoryBroker

from app.core.config import get_settings


def _make_broker() -> AsyncBroker:
    s = get_settings()
    if s.task_broker == "memory":
        return InMemoryBroker()
    from taskiq_redis import ListQueueBroker

    # BRPOP chờ task không giới hạn; redis-py ≥ 8 mặc định socket_timeout=5s → hàng đợi rỗng 5s là
    # receiver lỗi TimeoutError, process worker bị restart và giết luôn task ingest đang chạy.
    return ListQueueBroker(s.redis_url, socket_timeout=None)


broker = _make_broker()
