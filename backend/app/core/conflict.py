"""Conflict detection (detect + flag for manual review, never auto-merge)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Conflict


def classify_version_conflict(
    *,
    source_version: str,
    target_version: str,
    baseline_source: str,
    baseline_target: str,
) -> str:
    """Decide what to do given both sides' current versions and last-synced baselines.

    Returns one of:
    - ``idempotent``  : neither side changed since the last sync
    - ``source_newer``: only the source changed -> safe to push an update
    - ``target_newer``: only the target changed -> target wins, no action
    - ``conflict``    : both changed -> needs manual review
    """
    src_changed = source_version != baseline_source
    tgt_changed = target_version != baseline_target
    if src_changed and tgt_changed:
        return "conflict"
    if src_changed:
        return "source_newer"
    if tgt_changed:
        return "target_newer"
    return "idempotent"


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
