"""Authentication + role-based access control (#13).

Three roles, from least to most privileged:
- **viewer**   -> VIEWER_API_TOKEN: read-only (list/detail/metrics/audit).
- **operator** -> OPERATOR_API_TOKEN: viewer + operational actions (retry, resolve
  conflict, connectivity check, verify mapping, enqueue, SSRME, inbound pull).
- **admin**    -> ADMIN_API_TOKEN: operator + configuration changes (inbound policy
  create/delete) and everything else.

Backward compatible: if a role token is empty, that role simply does not exist
(an admin token always grants admin). Tokens are compared in constant time.
"""
from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import settings

_DEFAULT_TOKEN = "change_me_admin_token"

# Privilege ordering for hierarchy checks.
_ROLE_RANK = {"viewer": 1, "operator": 2, "admin": 3}


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


def resolve_role(token: str | None) -> str | None:
    """Return the role for a token, or None if invalid. Admin checked first."""
    if not token:
        return None
    if settings.admin_api_token and secrets.compare_digest(token, settings.admin_api_token):
        return "admin"
    if settings.operator_api_token and secrets.compare_digest(token, settings.operator_api_token):
        return "operator"
    if settings.viewer_api_token and secrets.compare_digest(token, settings.viewer_api_token):
        return "viewer"
    return None


async def current_role(authorization: str | None = Header(default=None)) -> str:
    """Resolve the caller's role or raise 401/403."""
    _check_default_guard()
    role = resolve_role(_bearer(authorization))
    if role is None:
        if _bearer(authorization) is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")
    return role


def _require_at_least(min_role: str):
    async def dep(authorization: str | None = Header(default=None)) -> str:
        role = await current_role(authorization)
        if _ROLE_RANK[role] < _ROLE_RANK[min_role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Butuh role minimal '{min_role}'")
        return role
    return dep


# Read access: viewer, operator, admin.
require_viewer = _require_at_least("viewer")
# Operational actions: operator, admin.
require_operator = _require_at_least("operator")
# Configuration / sensitive: admin only.
require_admin = _require_at_least("admin")
