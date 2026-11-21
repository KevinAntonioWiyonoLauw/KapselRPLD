"""Metrics endpoint (proposal 4.3.3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_operator
from app.core import metrics as prom
from app.db.session import get_db
from app.models import JobAttempt, SyncJob

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
async def metrics(db: Session = Depends(get_db), _: str = Depends(require_operator)):
    total = db.execute(select(func.count()).select_from(SyncJob)).scalar_one()
    by_status = dict(
        db.execute(select(SyncJob.status, func.count()).group_by(SyncJob.status)).all()
    )
    success = by_status.get("success", 0)
    processed = total
    success_rate = round((success / processed) * 100, 2) if processed else 0.0

    # Latency: avg (attempt.finished_at - job.created_at) for successful attempts
    rows = db.execute(
        select(SyncJob.created_at, JobAttempt.finished_at)
        .join(JobAttempt, JobAttempt.job_id == SyncJob.id)
        .where(JobAttempt.outcome == "success")
    ).all()
    latencies = [
        (f - c).total_seconds() for c, f in rows if c is not None and f is not None
    ]
    avg_latency = round(sum(latencies) / len(latencies), 3) if latencies else None

    return {
        "total_jobs": total,
        "by_status": by_status,
        "success_rate_percent": success_rate,
        "avg_latency_seconds": avg_latency,
        "duplicate_skips": db.execute(
            select(func.count()).select_from(JobAttempt).where(
                JobAttempt.error_detail.like("idempotent%"))
        ).scalar_one(),
    }


@router.get("/timeline")
async def metrics_timeline(db: Session = Depends(get_db), _: str = Depends(require_operator)):
    """Jobs per hour (last 24h) for trend charts."""
    rows = db.execute(
        select(func.date_trunc("hour", SyncJob.created_at).label("bucket"),
               func.count())
        .group_by("bucket").order_by("bucket")
    ).all()
    return [
        {"hour": b.isoformat() if b else None, "count": c}
        for b, c in rows
    ]


@router.get("/prometheus")
async def metrics_prometheus(db: Session = Depends(get_db)):
    """Prometheus exposition (scrape target). No auth: scraped internally.

    Refresh DB-derived gauges at scrape time so the values are correct regardless
    of which worker processed the jobs.
    """
    from fastapi import HTTPException
    from app.config import settings
    if not settings.metrics_enabled:
        raise HTTPException(404, "metrics disabled")
    prom.refresh_db_metrics(db)
    return Response(content=prom.render(), media_type="text/plain; version=0.0.4")
