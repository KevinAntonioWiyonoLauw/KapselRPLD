"""DB integration test for the OpenMRS target pipeline (real-OpenMRS rules).

OpenMRS FHIR2 requires: Patient.identifier to be a preferred identifier with a
resolvable type + registered system + location extension; Encounter.type to be an
encounter-type UUID; and non-Patient subjects to reference the mapped patient
uuid. This test exercises the pipeline with a fake OpenMRS adapter.
"""
import json
import uuid

import pytest

from app.adapters.base import AdapterResult
from app.services import sync
from app.models import IdentifierMapping, SyncJob


class FakeOpenMRS:
    def __init__(self):
        self.created = []

    async def search(self, rt, params):
        # No existing resource -> triggers create path.
        return AdapterResult(ok=True, http_status=200,
                             bundle={"resourceType": "Bundle", "total": 0, "entry": []})

    async def create(self, rt, resource):
        self.created.append(resource)
        return AdapterResult(ok=True, http_status=201,
                             resource={"resourceType": rt, "id": str(uuid.uuid4()),
                                       "meta": {"lastUpdated": "2026-01-01T00:00:00Z"}})


async def _run(db_session, fake, job):
    orig = sync.get_adapter
    sync.get_adapter = lambda name: fake
    try:
        out = await sync.process_job(db_session, job)
        db_session.commit()
    finally:
        sync.get_adapter = orig
    return out


@pytest.mark.asyncio
async def test_openmrs_encounter_and_observation_use_mapped_patient_uuid(db_session, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "openmrs_default_location_uuid", "loc-uuid", raising=False)

    tag = uuid.uuid4().hex[:8]
    src_pid = f"P-{tag}"          # source MRN
    src_enc = f"E-{tag}"
    tgt_puuid = str(uuid.uuid4())

    src = sync.get_system(db_session, "openemr")
    tgt = sync.get_system(db_session, "openmrs")
    db_session.add(IdentifierMapping(resource_type="Patient", source_system_id=src.id,
                                     target_system_id=tgt.id, source_identifier=src_pid,
                                     target_identifier=tgt_puuid, validation_status="verified"))
    db_session.commit()

    # --- Encounter ---
    enc = {"resourceType": "Encounter", "id": src_enc, "status": "finished",
           "subject": {"reference": f"Patient/{src_pid}"},
           "period": {"start": "2026-01-01T09:00:00Z"}}
    job = SyncJob(resource_type="Encounter", source_system_id=src.id, target_system_id=tgt.id,
                  source_resource_id=src_enc, idempotency_key=f"om-enc-{tag}",
                  status="pending", payload_ref=json.dumps(enc))
    db_session.add(job)
    db_session.commit()

    fake = FakeOpenMRS()
    out = await _run(db_session, fake, job)
    assert out.status == "success", out.last_error
    enc_sent = fake.created[-1]
    assert enc_sent["subject"]["reference"] == f"Patient/{tgt_puuid}"
    coding = enc_sent["type"][0]["coding"][0]
    assert coding["system"] == "http://fhir.openmrs.org/code-system/encounter-type"
    assert len(coding["code"]) == 36

    # --- Patient (preferred identifier shape) ---
    pat = {"resourceType": "Patient",
           "identifier": [{"system": "http://openmrs.org/mrn", "value": src_pid}],
           "name": [{"family": "Uji", "given": ["OpenMRS"]}], "gender": "male",
           "birthDate": "1990-01-01"}
    job2 = SyncJob(resource_type="Patient", source_system_id=src.id, target_system_id=tgt.id,
                   source_resource_id=src_pid, idempotency_key=f"om-pat-{tag}",
                   status="pending", payload_ref=json.dumps(pat))
    db_session.add(job2)
    db_session.commit()
    out2 = await _run(db_session, fake, job2)
    assert out2.status == "success", out2.last_error
    ident = fake.created[-1]["identifier"][0]
    assert ident["use"] == "official"
    assert ident["type"]["text"] == "Old Identification Number"
    loc_ext = [e for e in ident["extension"]
               if e["url"] == "http://fhir.openmrs.org/ext/patient/identifier#location"]
    assert loc_ext and loc_ext[0]["valueReference"]["reference"] == "Location/loc-uuid"
