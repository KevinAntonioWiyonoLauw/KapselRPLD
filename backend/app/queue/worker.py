"""Background worker: claims due jobs (DB-backed, FOR UPDATE SKIP LOCKED) and
processes them. Run as: python -m app.queue.worker
"""
from __future__ import annotations

import asyncio
import logging
import signal

from sqlalchemy import func, or_, select

from app.config import settings
from app.db.session import SessionLocal, init_db
from app.models import SyncJob
from app.services.sync import process_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(levelname)s %(message)s")
log = logging.getLogger("worker")

_stop = False


def _claim_one(db) -> SyncJob | None:
    stmt = (
        select(SyncJob)
        .where(
            SyncJob.status.in_(["pending", "failed_temp"]),
            or_(SyncJob.next_attempt_at.is_(None), SyncJob.next_attempt_at <= func.now()),
        )
        .order_by(SyncJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = db.execute(stmt).scalar_one_or_none()
    if job:
        job.status = "processing"
        db.commit()
        db.refresh(job)
    return job


async def _run_once() -> bool:
    """Process at most one due job. Returns True if a job was handled."""
    db = SessionLocal()
    try:
        job = _claim_one(db)
        if not job:
            return False
        log.info("processing job %s (%s -> %s)", job.id, job.resource_type, job.target_system_id)
        await process_job(db, job)
        # Privacy: clear stored clinical payload after success (metadata retained).
        if settings.payload_retention_on_success and job.status == "success":
            job.payload_ref = None
        db.commit()
        return True
    finally:
        db.close()


async def main() -> None:
    init_db()
    log.info("worker started (poll=%ss)", settings.worker_poll_seconds)
    while not _stop:
        try:
            did_work = await _run_once()
        except Exception:  # noqa: BLE001
            log.exception("worker loop error")
            did_work = False
        if not did_work:
            await asyncio.sleep(settings.worker_poll_seconds)


def _handle_sigterm(*_):
    global _stop
    _stop = True


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)
    asyncio.run(main())
