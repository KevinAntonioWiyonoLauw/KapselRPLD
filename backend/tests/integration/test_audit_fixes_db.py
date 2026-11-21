"""Regression tests (DB) for audit fix F2 — error classification in process_job.

Run with DB access (compose network):
    python -m pytest tests/integration/test_audit_fixes_db.py
"""
import uuid
from unittest.mock import patch

import pytest

from app.services import sync


def _mk_job(db, src_name="openmrs", tgt_name="openemr"):
    src = sync.get_system(db, src_name)
    tgt = sync.get_system(db, tgt_name)
    job = sync.SyncJob(
        resource_type="Patient",
        source_system_id=src.id,
        target_system_id=tgt.id,
        source_resource_id="REGTEST-1",
        idempotency_key=f"reg-{uuid.uuid4().hex}",
        status="pending",
        payload_ref='{"resourceType":"Patient","identifier":[{"system":"http://openmrs.org/mrn","value":"REGTEST-1"}]}',
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@pytest.mark.asyncio
async def test_f2_programming_error_fails_perm_not_retry(db_session):
    job = _mk_job(db_session)
    with patch.object(sync, "get_adapter", side_effect=NameError("boom")):
        out = await sync.process_job(db_session, job)
    db_session.commit()
    assert out.status == "failed_perm"
    assert "Unhandled" in (out.last_error or "")


@pytest.mark.asyncio
async def test_f2_retryable_timeout_is_failed_temp(db_session):
    job = _mk_job(db_session)
    with patch.object(sync, "get_adapter", side_effect=TimeoutError("slow")):
        out = await sync.process_job(db_session, job)
    db_session.commit()
    assert out.status == "failed_temp"
    assert out.next_attempt_at is not None
