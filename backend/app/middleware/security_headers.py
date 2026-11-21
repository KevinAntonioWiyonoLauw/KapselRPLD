"""Security response headers (#17).

Adds defensive headers to every response. A strict Content-Security-Policy is
applied to the API surface; interactive docs (/docs, /openapi.json) are exempt so
Swagger UI keeps working. HSTS is only sent over HTTPS (or behind a TLS proxy
advertising ``X-Forwarded-Proto: https``).
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

# Paths that serve an HTML UI and therefore must not get the strict API CSP.
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

_STRICT_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        path = request.url.path
        if not any(path == p or path.startswith(p + "/") or path.startswith(p)
                   for p in _DOCS_PATHS):
            h.setdefault("Content-Security-Policy", _STRICT_CSP)
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto == "https":
            h.setdefault("Strict-Transport-Security",
                         f"max-age={settings.hsts_max_age}; includeSubDomains")
        return response
