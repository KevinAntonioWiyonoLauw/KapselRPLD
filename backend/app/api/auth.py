"""Authentication endpoints (#13): token login + whoami.

The dashboard "login" exchanges a role token for the role name, so the UI can show
the current role and gate actions. Tokens are still sent as Bearer on each request
(stateless); this endpoint does not issue new tokens.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import current_role, resolve_role
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    token: str


@router.post("/login")
async def login(payload: LoginRequest):
    role = resolve_role(payload.token)
    if role is None:
        from fastapi import HTTPException
        raise HTTPException(401, "Token tidak valid")
    return {"ok": True, "role": role}


@router.get("/me")
async def me(role: str = Depends(current_role)):
    return {"role": role}


@router.get("/roles")
async def roles():
    """Which roles are configured (no secrets)."""
    return {
        "admin": bool(settings.admin_api_token),
        "operator": bool(settings.operator_api_token),
        "viewer": bool(settings.viewer_api_token),
    }
