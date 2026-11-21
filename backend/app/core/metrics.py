"""Prometheus metrics for the middleware (#16).

Two complementary sources are exposed at ``/metrics/prometheus``:
- Gauges computed from the database at scrape time (job counts by status, conflicts
  pending, duplicate skips, success rate, avg latency). Correct across all workers.
- Counters incremented in-process as jobs are processed (throughput/latency/errors),
  labelled by resource type / target / status.
"""
from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, generate_latest

# Dedicated registry so /metrics/prometheus only exposes our metrics (not the
# default process/platform collectors, which would add noise).
REGISTRY = CollectorRegistry()

JOBS_TOTAL = Counter(
    "kapsel_jobs_total", "Sync jobs processed (this process)",
    ["resource_type", "target", "status"], registry=REGISTRY)
JOB_DURATION = Counter(
    "kapsel_job_duration_seconds_total", "Cumulative job processing time (this process)",
    ["resource_type", "target"], registry=REGISTRY)

DB_JOBS_BY_STATUS = Gauge(
    "kapsel_jobs_by_status", "Sync jobs by status (from DB)", ["status"], registry=REGISTRY)
DB_TOTAL_JOBS = Gauge("kapsel_jobs_total_db", "Total sync jobs (from DB)", registry=REGISTRY)
DB_CONFLICTS_PENDING = Gauge(
    "kapsel_conflicts_pending", "Conflicts awaiting review (from DB)", registry=REGISTRY)
DB_DUPLICATE_SKIPS = Gauge(
    "kapsel_duplicate_skips", "Idempotent duplicate skips (from DB)", registry=REGISTRY)
DB_SUCCESS_RATE = Gauge(
    "kapsel_success_rate_percent", "Success rate percent (from DB)", registry=REGISTRY)


def record_job(resource_type: str, target: str, status: str, duration_s: float | None = None) -> None:
    JOBS_TOTAL.labels(resource_type=resource_type or "unknown",
                      target=target or "unknown", status=status or "unknown").inc()
    if duration_s is not None:
        JOB_DURATION.labels(resource_type=resource_type or "unknown",
                            target=target or "unknown").inc(duration_s)


def refresh_db_metrics(db) -> None:
    from sqlalchemy import func, select
    from app.models import Conflict, JobAttempt, SyncJob

    total = db.execute(select(func.count()).select_from(SyncJob)).scalar_one()
    by_status = dict(db.execute(select(SyncJob.status, func.count()).group_by(SyncJob.status)).all())
    DB_TOTAL_JOBS.set(total)
    for status, n in by_status.items():
        DB_JOBS_BY_STATUS.labels(status=status).set(n)
    success = by_status.get("success", 0)
    DB_SUCCESS_RATE.set(round((success / total) * 100, 2) if total else 0.0)
    DB_CONFLICTS_PENDING.set(db.execute(
        select(func.count()).select_from(Conflict).where(Conflict.resolution == "pending")
    ).scalar_one())
    DB_DUPLICATE_SKIPS.set(db.execute(
        select(func.count()).select_from(JobAttempt).where(JobAttempt.error_detail.like("idempotent%"))
    ).scalar_one())


def render() -> bytes:
    return generate_latest(REGISTRY)
