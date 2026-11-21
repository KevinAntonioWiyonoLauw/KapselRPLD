"""HTTPS redirect + trusted-host middleware (#17).

- ``HTTPSRedirectMiddleware``: when ``FORCE_HTTPS=true`` (set this in production,
  behind a TLS-terminating proxy), redirect plain HTTP to HTTPS.
- ``TrustedHostMiddleware``: when ``ALLOWED_HOSTS`` is set (comma separated),
  reject requests whose Host header is not in the allowlist (DNS-rebinding / Host
  header attack protection).

Health checks are exempt from the HTTPS redirect so container orchestrators can
probe over the internal network.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from app.config import settings

_HEALTH_PATHS = ("/health", "/")


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if settings.force_https and request.method in ("GET", "HEAD"):
            proto = request.headers.get("x-forwarded-proto", request.url.scheme)
            if proto != "https" and request.url.path not in _HEALTH_PATHS:
                url = request.url.replace(scheme="https")
                return RedirectResponse(str(url), status_code=307)
        return await call_next(request)
