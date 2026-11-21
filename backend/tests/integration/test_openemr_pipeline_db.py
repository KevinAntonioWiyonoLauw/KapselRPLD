"""DB integration test for the OpenEMR Observation -> Encounter dependency (#7).

OpenEMR stores Observations as encounter forms, so the pipeline must resolve the
source Encounter to its mapped target id and pass it as Observation.encounter, and
must NOT search Observations with the unsupported `subject` param.
"""
import json
import uuid

import pytest

from app.adapters.base import AdapterResult
from app.services import sync
from app.models import IdentifierMapping, SyncJob


class FakeOpenEMR:
    def __init__(self):
        self.search_called = False
        self.captured = None

    async def search(self, rt, params):
        self.search_called = True
        return AdapterResult(ok=True, http_status=200,
                             bundle={"resourceType": "Bundle", "total": 0, "entry": []})

    async def create(self, rt, resource):
        self.captured = resource
        return AdapterResult(ok=True, http_status=201,
                             resource={"resourceType": rt, "id": "obs-uuid",
                                       "meta": {"lastUpdated": "2026-01-01T00:00:00Z"}})


@pytest.mark.asyncio
async def test_openemr_observation_gets_mapped_encounter_ref(db_session):
    tag = uuid.uuid4().hex[:8]
    src_pid = f"P-{tag}"
    src_enc = f"E-{tag}"
    tgt_puuid = str(uuid.uuid4())
    tgt_euuid = str(uuid.uuid4())

    src = sync.get_system(db_session, "openmrs")
    tgt = sync.get_system(db_session, "openemr")
    db_session.add(IdentifierMapping(resource_type="Patient", source_system_id=src.id,
                                     target_system_id=tgt.id, source_identifier=src_pid,
                                     target_identifier=tgt_puuid, validation_status="verified"))
    db_session.add(IdentifierMapping(resource_type="Encounter", source_system_id=src.id,
                                     target_system_id=tgt.id, source_identifier=src_enc,
                                     target_identifier=tgt_euuid, validation_status="verified"))
    db_session.commit()

    obs = {
        "resourceType": "Observation", "status": "final",
        "subject": {"reference": f"Patient/{src_pid}"},
        "encounter": {"reference": f"Encounter/{src_enc}"},
        "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
        "valueQuantity": {"value": 80, "unit": "/min"},
        "effectiveDateTime": "2026-01-01T09:00:00Z",
    }
    job = SyncJob(resource_type="Observation", source_system_id=src.id, target_system_id=tgt.id,
                  source_resource_id=src_enc, idempotency_key=f"oe-{uuid.uuid4().hex}",
                  status="pending", payload_ref=json.dumps(obs))
    db_session.add(job)
    db_session.commit()

    fake = FakeOpenEMR()
    orig = sync.get_adapter
    sync.get_adapter = lambda name: fake
    try:
        out = await sync.process_job(db_session, job)
        db_session.commit()
    finally:
        sync.get_adapter = orig

    assert out.status == "success"
    assert fake.search_called is False  # OpenEMR obs search skipped (no subject param)
    assert fake.captured["encounter"]["reference"] == f"Encounter/{tgt_euuid}"
    assert fake.captured["subject"]["reference"] == f"Patient/{tgt_puuid}"
    assert fake.captured["category"][0]["coding"][0]["code"] == "vital-signs"
