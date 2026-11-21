"""Simple in-memory rate limiting for the Management API (per client IP).

Disabled by default (settings.rate_limit_per_minute == 0).
Note: per-process; adequate for a single-instance prototype.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        limit = settings.rate_limit_per_minute
        if limit and request.url.path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            now = time.time()
            q = self._hits[ip]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= limit:
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
            q.append(now)
        return await call_next(request)
