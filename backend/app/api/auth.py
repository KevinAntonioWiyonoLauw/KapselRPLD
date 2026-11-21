"""Authentication endpoints (#13): login form (username+password) + token login + whoami.

Dua jalur login:

- **Form (default dashboard)**: ``POST /auth/login`` dengan ``{username, password}``.
  Kredensial demo per peran didefinisikan di ``.env`` (``ADMIN_USERNAME``/``ADMIN_PASSWORD``
  dst). Bila cocok, server mengembalikan ``role`` **dan** ``token`` (API token peran itu).
  Frontend menyimpan token di cookie (httpOnly via Next route handler) lalu mengirim
  ``Authorization: Bearer <token>`` seperti biasa — RBAC backend tetap berlaku penuh.
- **Token (backward compatible / API)**: ``POST /auth/login`` dengan ``{token}``
  menukar token -> role (tidak menerbitkan token baru).

Password dibandingkan constant-time. Token yang dikembalikan adalah API token peran
(``ADMIN_API_TOKEN`` dst) sehingga tetap stateless untuk request berikutnya.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import current_role, resolve_role
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    # Form login (username + password) atau token (kompatibel lama).
    username: str | None = None
    password: str | None = None
    token: str | None = None


def _demo_accounts() -> list[tuple[str, str, str, str]]:
    """Return (role, username, password, api_token) for configured demo accounts.

    An account is active only when username + password + the role's API token are
    all non-empty. Admin token defaults to a placeholder so admin is active by default.
    """
    return [
        ("admin", settings.admin_username, settings.admin_password, settings.admin_api_token),
        ("operator", settings.operator_username, settings.operator_password, settings.operator_api_token),
        ("viewer", settings.viewer_username, settings.viewer_password, settings.viewer_api_token),
    ]


def _match_demo_account(username: str, password: str) -> tuple[str, str] | None:
    """Constant-time-ish check of username+password -> (role, api_token)."""
    for role, u, p, tok in _demo_accounts():
        if not u or not p or not tok:
            continue
        u_ok = secrets.compare_digest(username, u)
        p_ok = secrets.compare_digest(password, p)
        if u_ok and p_ok:
            return role, tok
    return None


@router.post("/login")
async def login(payload: LoginRequest):
    # 1) Form login: username + password -> role + token.
    if payload.username is not None and payload.password is not None:
        match = _match_demo_account(payload.username, payload.password)
        if match is None:
            raise HTTPException(401, "Username atau password salah")
        role, token = match
        return {"ok": True, "role": role, "token": token}

    # 2) Token login (kompatibel lama / API): token -> role.
    if payload.token:
        role = resolve_role(payload.token)
        if role is None:
            raise HTTPException(401, "Token tidak valid")
        return {"ok": True, "role": role, "token": payload.token}

    raise HTTPException(422, "Isi username+password atau token")


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
