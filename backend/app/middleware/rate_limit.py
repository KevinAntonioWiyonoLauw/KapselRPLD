"""Rate limiting for the Management API (per client IP).

Two backends:
- **memory** (default): per-process sliding window. Fine for a single instance.
- **redis** (``RATE_LIMIT_BACKEND=redis``): shared fixed-window counters across
  instances, so limits hold when the API runs behind a load balancer / multiple
  replicas. Uses ``INCR`` + ``EXPIRE`` (atomic; first request of a window sets TTL).

Disabled entirely when ``RATE_LIMIT_PER_MINUTE == 0``. If the Redis backend is
selected but Redis is unreachable, it fails **open** (allows the request) and logs
a warning, so a cache outage never takes the API down.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

log = logging.getLogger("ratelimit")


class MemoryStore:
    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)

    def hit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        now = time.time()
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            retry = int(window - (now - q[0])) if q else window
            return False, max(retry, 1)
        q.append(now)
        return True, 0


class RedisStore:
    def __init__(self, url: str) -> None:
        import redis  # lazy import so redis is optional at runtime
        self._client = redis.Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)

    def hit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        bucket = int(time.time() // window)
        rkey = f"rl:{key}:{bucket}"
        count = self._client.incr(rkey)
        if count == 1:
            self._client.expire(rkey, window)
        if count > limit:
            ttl = self._client.ttl(rkey)
            return False, max(int(ttl), 1)
        return True, 0


def _build_store():
    backend = (settings.rate_limit_backend or "memory").lower()
    if backend == "redis" and settings.redis_url:
        try:
            return RedisStore(settings.redis_url)
        except Exception as exc:  # noqa: BLE001
            log.warning("redis rate-limit store unavailable, falling back to memory: %s", exc)
    return MemoryStore()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._store = _build_store()
        self._window = 60

    async def dispatch(self, request: Request, call_next):
        limit = settings.rate_limit_per_minute
        if limit and request.url.path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            try:
                allowed, retry = self._store.hit(ip, limit, self._window)
            except Exception as exc:  # noqa: BLE001  (fail open)
                log.warning("rate-limit store error (fail open): %s", exc)
                return await call_next(request)
            if not allowed:
                return JSONResponse(
                    {"detail": "Rate limit exceeded"},
                    status_code=429, headers={"Retry-After": str(retry)})
        return await call_next(request)
