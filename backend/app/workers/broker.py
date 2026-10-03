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

    return ListQueueBroker(s.redis_url)


broker = _make_broker()
