"""Audit log helper with basic sanitisation of sensitive fields."""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models import AuditLog

_SENSITIVE_KEYS = {"password", "secret", "token", "authorization", "client_secret"}


def _sanitize(data: dict | None) -> dict | None:
    if not data:
        return data
    out = {}
    for k, v in data.items():
        if k.lower() in _SENSITIVE_KEYS:
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = _sanitize(v)
        elif isinstance(v, str) and len(v) > 1000:
            out[k] = v[:1000] + "...[truncated]"
        else:
            out[k] = v
    return out


def log(
    db: Session,
    *,
    actor: str,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: dict | None = None,
    correlation_id=None,
) -> None:
    entry = AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        detail_json=_sanitize(detail),
        correlation_id=correlation_id,
    )
    db.add(entry)
