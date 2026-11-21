"""Sync job endpoints: list, detail, retry, and a demo enqueue trigger."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_operator, require_viewer
from app.audit import logger as audit
from app.db.session import get_db
from app.models import JobAttempt, SyncJob
from app.schemas import EnqueueRequest
from app.services.sync import enqueue_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_dict(j: SyncJob) -> dict:
    return {
        "id": str(j.id),
        "resource_type": j.resource_type,
        "status": j.status,
        "attempt_count": j.attempt_count,
        "source_resource_id": j.source_resource_id,
        "last_error": j.last_error,
        "next_attempt_at": j.next_attempt_at.isoformat() if j.next_attempt_at else None,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
    }


@router.get("")
async def list_jobs(
    status: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _: str = Depends(require_viewer),
):
    stmt = select(SyncJob).order_by(SyncJob.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(SyncJob.status == status)
    if resource_type:
        stmt = stmt.where(SyncJob.resource_type == resource_type)
    jobs = db.execute(stmt).scalars().all()
    return [_job_dict(j) for j in jobs]


@router.get("/{job_id}")
async def get_job(job_id: str, db: Session = Depends(get_db), _: str = Depends(require_viewer)):
    job = db.get(SyncJob, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    attempts = db.execute(
        select(JobAttempt).where(JobAttempt.job_id == job.id).order_by(JobAttempt.attempt_no)
    ).scalars().all()
    data = _job_dict(job)
    data["attempts"] = [
        {"attempt_no": a.attempt_no, "outcome": a.outcome, "http_status": a.http_status,
         "error_detail": a.error_detail}
        for a in attempts
    ]
    return data


@router.post("/{job_id}/retry")
async def retry_job(job_id: str, db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    job = db.get(SyncJob, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job.status not in ("failed_temp", "failed_perm", "needs_review"):
        raise HTTPException(400, f"Job berstatus '{job.status}' tidak dapat di-retry")
    job.status = "pending"
    job.next_attempt_at = None
    audit.log(db, actor=actor, action="manual_retry", entity_type="SyncJob", entity_id=job.id)
    db.commit()
    return {"ok": True, "id": str(job.id), "status": job.status}


@router.post("/enqueue")
async def enqueue(payload: EnqueueRequest, db: Session = Depends(get_db), _: str = Depends(require_operator)):
    """Demo/dev helper: enqueue a resource for sync."""
    try:
        job = enqueue_job(
            db, source_name=payload.source_system, target_name=payload.target_system,
            resource=payload.resource, version=payload.version,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.commit()
    return {"ok": True, "job_id": str(job.id), "status": job.status}
