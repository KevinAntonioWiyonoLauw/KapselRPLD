"""Admin authentication dependency with lightweight RBAC.

Roles:
- admin   -> ADMIN_API_TOKEN (full access, including sensitive endpoints)
- operator-> OPERATOR_API_TOKEN (retry/resolve/check/mapping verify; optional)
If OPERATOR_API_TOKEN is empty, only admin exists (operator falls back to admin).
"""
from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import settings

_DEFAULT_TOKEN = "change_me_admin_token"


def _bearer(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip()


def _check_default_guard() -> None:
    if settings.admin_api_token == _DEFAULT_TOKEN and settings.app_env != "development":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_API_TOKEN masih default; set token kuat sebelum non-dev",
        )


async def require_admin(authorization: str | None = Header(default=None)) -> str:
    _check_default_guard()
    token = _bearer(authorization)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    if not secrets.compare_digest(token, settings.admin_api_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")
    return "admin"


async def require_operator(authorization: str | None = Header(default=None)) -> str:
    """Admin or operator role."""
    _check_default_guard()
    token = _bearer(authorization)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    if secrets.compare_digest(token, settings.admin_api_token):
        return "admin"
    if settings.operator_api_token and secrets.compare_digest(token, settings.operator_api_token):
        return "operator"
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")
