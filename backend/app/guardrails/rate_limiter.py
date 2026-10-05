"""Rate limit theo cửa sổ thời gian (mặc định 30 request/phút/user)."""
import time
from collections import defaultdict, deque
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings


class RateLimiter(Protocol):
    async def hit(self, key: str) -> bool:
        """Ghi nhận một request; True nếu còn trong hạn mức."""
        ...


class MemoryRateLimiter:
    """Sliding window trong process (dev/test)."""

    def __init__(self, limit: int, window_seconds: float = 60.0):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def hit(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


class RedisRateLimiter:
    """Fixed window trên Redis (INCR + EXPIRE), dùng chung giữa nhiều process API."""

    def __init__(self, redis_url: str, limit: int, window_seconds: int = 60):
        from redis.asyncio import from_url

        self.redis = from_url(redis_url)
        self.limit = limit
        self.window = window_seconds

    async def hit(self, key: str) -> bool:
        bucket = f"ratelimit:{key}:{int(time.time() // self.window)}"
        async with self.redis.pipeline(transaction=True) as pipe:
            count, _ = await pipe.incr(bucket).expire(bucket, self.window, nx=True).execute()
        return count <= self.limit


@lru_cache
def get_rate_limiter() -> RateLimiter:
    s = get_settings()
    if s.rate_limit_backend == "memory":
        return MemoryRateLimiter(s.rate_limit_per_minute)
    return RedisRateLimiter(s.redis_url, s.rate_limit_per_minute)
