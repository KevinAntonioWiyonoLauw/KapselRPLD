"""DB integration tests for Observation idempotency (issue #2).

Two identical Observations (same subject+code+effective) must produce a single
entity in the target thanks to search-before-create. Uses fake adapters + DB.
"""
import json
import uuid

import pytest

from app.adapters.base import AdapterResult
from app.services import sync
from app.models import IdentifierMapping, SyncJob


class FakeObsAdapter:
    def __init__(self):
        self.store = {}
        self.create_count = 0

    async def search(self, rt, params):
        matches = [r for r in self.store.values()
                   if params.get("subject") == (r.get("subject") or {}).get("reference")
                   and params.get("code") == ((r.get("code") or {}).get("coding") or [{}])[0].get("code")
                   and params.get("date") == (r.get("effectiveDateTime") or r.get("issued"))]
        return AdapterResult(ok=True, http_status=200,
                             bundle={"resourceType": "Bundle", "total": len(matches),
                                     "entry": [{"resource": r} for r in matches]})

    async def create(self, rt, resource):
        self.create_count += 1
        rid = f"obs-{self.create_count}"
        stored = {**resource, "id": rid, "meta": {"lastUpdated": "2026-01-01T00:00:00Z"}}
        self.store[rid] = stored
        return AdapterResult(ok=True, http_status=201, resource=stored)


def _mk_job(db, obs):
    src = sync.get_system(db, "openmrs")
    tgt = sync.get_system(db, "openemr")
    job = SyncJob(resource_type="Observation", source_system_id=src.id, target_system_id=tgt.id,
                  source_resource_id="enc-1", idempotency_key=f"obs-{uuid.uuid4().hex}",
                  status="pending", payload_ref=json.dumps(obs))
    db.add(job)
    db.commit()
    return job


@pytest.mark.asyncio
async def test_identical_observation_not_duplicated(db_session):
    pid = f"P{uuid.uuid4().hex[:8]}"
    obs = {
        "resourceType": "Observation",
        "status": "final",
        "subject": {"reference": f"Patient/{pid}"},
        "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
        "effectiveDateTime": "2026-03-01T09:00:00Z",
        "valueQuantity": {"value": 80, "unit": "/min"},
    }
    # Observation -> OpenEMR needs a verified Patient mapping for subject resolution.
    src = sync.get_system(db_session, "openmrs")
    tgt = sync.get_system(db_session, "openemr")
    db_session.add(IdentifierMapping(
        resource_type="Patient", source_system_id=src.id, target_system_id=tgt.id,
        source_identifier=pid, target_identifier=pid, validation_status="verified"))
    db_session.commit()

    fake = FakeObsAdapter()
    orig = sync.get_adapter
    sync.get_adapter = lambda name: fake
    try:
        j1 = _mk_job(db_session, obs)
        out1 = await sync.process_job(db_session, j1)
        db_session.commit()
        assert out1.status == "success"

        # Same business key (different source id) must NOT create a duplicate.
        j2 = _mk_job(db_session, obs)
        out2 = await sync.process_job(db_session, j2)
        db_session.commit()
        assert out2.status == "success"
    finally:
        sync.get_adapter = orig

    assert fake.create_count == 1
    assert len(fake.store) == 1
