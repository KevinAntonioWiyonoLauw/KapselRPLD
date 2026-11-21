"""DB integration tests for version-based conflict detection (issue #1 / F4).

Drives ``process_job`` with fake adapters to exercise the three version branches:
source-newer -> update, both-changed -> conflict, target-newer -> no action.
Requires DB access (compose network).
"""
import json
import uuid
from unittest.mock import patch

import pytest

from app.adapters.base import AdapterResult
from app.services import sync
from app.models import Conflict, IdentifierMapping, SyncJob

MRN = "http://openmrs.org/mrn"


class FakeAdapter:
    def __init__(self, existing_meta):
        self.existing_meta = existing_meta
        self.updated = None
        self.created = False

    async def search(self, rt, params):
        existing = {"resourceType": "Patient", "id": "TGT-1",
                    "identifier": [{"system": MRN, "value": "F4-1"}],
                    "name": [{"family": "Existing"}], "gender": "male",
                    "meta": {"lastUpdated": self.existing_meta}}
        return AdapterResult(ok=True, http_status=200,
                             bundle={"resourceType": "Bundle", "total": 1,
                                     "entry": [{"resource": existing}]})

    async def update(self, rt, rid, resource):
        self.updated = (rt, rid)
        return AdapterResult(ok=True, http_status=200,
                             resource={**resource, "id": rid, "meta": {"lastUpdated": "TGT-NEW"}})

    async def create(self, rt, resource):
        self.created = True
        return AdapterResult(ok=True, http_status=201,
                             resource={**resource, "id": "NEW", "meta": {"lastUpdated": "TGT-NEW"}})


def _mk(db, src_ver, base_src, base_tgt):
    src = sync.get_system(db, "openmrs")
    tgt = sync.get_system(db, "openemr")
    ident = f"F4-{uuid.uuid4().hex[:8]}"
    resource = {"resourceType": "Patient",
                "identifier": [{"system": MRN, "value": ident}],
                "name": [{"family": "Incoming"}], "gender": "male",
                "meta": {"lastUpdated": src_ver}}
    job = SyncJob(resource_type="Patient", source_system_id=src.id, target_system_id=tgt.id,
                  source_resource_id=ident, idempotency_key=f"f4-{uuid.uuid4().hex}",
                  status="pending", payload_ref=json.dumps(resource))
    db.add(job)
    db.flush()
    db.add(IdentifierMapping(resource_type="Patient", source_system_id=src.id,
                             target_system_id=tgt.id, source_identifier=ident,
                             target_identifier="TGT-1", identifier_type="local",
                             validation_status="verified",
                             synced_version=base_src, synced_target_version=base_tgt))
    db.commit()
    return job


@pytest.mark.asyncio
async def test_source_newer_triggers_update(db_session):
    job = _mk(db_session, src_ver="v2", base_src="v1", base_tgt="t1")
    fake = FakeAdapter(existing_meta="t1")  # target unchanged
    with patch.object(sync, "get_adapter", return_value=fake):
        out = await sync.process_job(db_session, job)
    db_session.commit()
    assert out.status == "success"
    assert fake.updated == ("Patient", "TGT-1")
    assert fake.created is False


@pytest.mark.asyncio
async def test_both_changed_records_conflict(db_session):
    job = _mk(db_session, src_ver="v2", base_src="v1", base_tgt="t1")
    fake = FakeAdapter(existing_meta="t2")  # target also changed
    with patch.object(sync, "get_adapter", return_value=fake):
        out = await sync.process_job(db_session, job)
    db_session.commit()
    assert out.status == "needs_review"
    assert fake.updated is None
    rows = db_session.query(Conflict).filter(Conflict.job_id == job.id).all()
    assert len(rows) == 1 and rows[0].resolution == "pending"


@pytest.mark.asyncio
async def test_target_newer_no_action(db_session):
    job = _mk(db_session, src_ver="v1", base_src="v1", base_tgt="t1")
    fake = FakeAdapter(existing_meta="t2")  # only target changed
    with patch.object(sync, "get_adapter", return_value=fake):
        out = await sync.process_job(db_session, job)
    db_session.commit()
    assert out.status == "success"
    assert fake.updated is None
    assert db_session.query(Conflict).filter(Conflict.job_id == job.id).count() == 0
