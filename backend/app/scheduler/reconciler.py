"""Reconciliation: recover jobs stuck in 'processing' (e.g. worker crashed)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import SyncJob

log = logging.getLogger("reconciler")


def reconcile_once(stuck_minutes: int = 15) -> int:
    db = SessionLocal()
    recovered = 0
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stuck_minutes)
        jobs = db.execute(
            select(SyncJob).where(SyncJob.status == "processing", SyncJob.updated_at < cutoff)
        ).scalars().all()
        for job in jobs:
            job.status = "failed_temp"
            job.last_error = "Reconciler: job stuck in processing; requeued"
            recovered += 1
        db.commit()
    finally:
        db.close()
    if recovered:
        log.info("reconciler requeued %d stuck jobs", recovered)
    return recovered
