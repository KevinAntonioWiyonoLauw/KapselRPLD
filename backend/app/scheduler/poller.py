"""Polling: check source systems for changes and enqueue sync jobs.

Polls every enabled EHR source (OpenMRS / OpenEMR) per enabled policy and
enqueues sync jobs to the policy target. Uses _lastUpdated to fetch recent changes.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.adapters.registry import get_adapter
from app.config import settings
from app.db.session import SessionLocal
from app.models import ExternalSystem, SyncPolicy
from app.scheduler.timeutil import fhir_last_updated
from app.services.sync import enqueue_job, get_system

log = logging.getLogger("poller")

EHR_SYSTEMS = {"openmrs", "openemr"}


async def poll_once(lookback_minutes: int = 10) -> int:
    """Poll enabled source systems once. Returns number of jobs enqueued."""
    enqueued = 0
    db = SessionLocal()
    try:
        policies = db.execute(
            select(SyncPolicy).where(SyncPolicy.enabled.is_(True))
        ).scalars().all()
        since = fhir_last_updated(lookback_minutes=lookback_minutes)

        for policy in policies:
            source = db.get(ExternalSystem, policy.source_system_id)
            target = db.get(ExternalSystem, policy.target_system_id)
            if not source or not target:
                continue
            if source.name not in EHR_SYSTEMS:
                continue  # poll only EHR systems (not SATUSEHAT)
            adapter = get_adapter(source.name)
            res = await adapter.search(policy.resource_type, {"_lastUpdated": f"gt{since}"})
            if not res.ok or not res.bundle:
                continue
            for entry in res.bundle.get("entry", []):
                resource = entry.get("resource")
                if not resource:
                    continue
                version = resource.get("meta", {}).get("lastUpdated", "")
                job = enqueue_job(
                    db, source_name=source.name, target_name=target.name,
                    resource=resource, policy_id=policy.id, version=version,
                )
                if job.status == "pending":
                    enqueued += 1
        db.commit()
    finally:
        db.close()
    return enqueued
