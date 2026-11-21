"""Conflict detection (detect + flag for manual review, never auto-merge)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Conflict


def detect_version_conflict(
    db: Session,
    *,
    job_id,
    resource_type: str,
    source_version: str | None,
    target_version: str | None,
) -> Conflict | None:
    """Record a conflict when source and target versions differ in an update flow."""
    if source_version and target_version and source_version != target_version:
        conflict = Conflict(
            job_id=job_id,
            resource_type=resource_type,
            source_version=source_version,
            target_version=target_version,
            resolution="pending",
            note="Versi sumber dan tujuan berbeda; perlu peninjauan manual.",
        )
        db.add(conflict)
        db.flush()
        return conflict
    return None
