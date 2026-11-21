"""DB integration test: SATUSEHAT Encounter pipeline maps every source diagnosis
into its own Condition resource (#10).

Uses a fake SATUSEHAT adapter to capture the transaction bundle sent by the
automatic pipeline (`_process_satusehat`), so we can assert the Condition count
and the Encounter.diagnosis references without a real sandbox.
"""
import json
import uuid

import pytest

from app.adapters.base import AdapterResult
from app.config import settings
from app.services import sync
from app.models import IdentifierMapping, SyncJob


class FakeSatusehat:
    def __init__(self):
        self.captured_bundle = None

    async def read(self, rt, rid):
        return AdapterResult(ok=True, http_status=200, resource={"resourceType": rt, "id": rid})

    async def search(self, rt, params):
        return AdapterResult(ok=True, http_status=200,
                             bundle={"resourceType": "Bundle", "total": 0, "entry": []})

    async def create(self, rt, resource):
        return AdapterResult(ok=True, http_status=201, resource={"resourceType": rt, "id": "loc-1"})

    async def transaction(self, bundle):
        self.captured_bundle = bundle
        return AdapterResult(ok=True, http_status=200, resource={
            "resourceType": "Bundle", "type": "transaction-response",
            "entry": [
                {"response": {"location": "Encounter/enc-real-1"}},
                {"response": {"location": "Condition/cond-real-1"}},
                {"response": {"location": "Condition/cond-real-2"}},
            ],
        })


@pytest.mark.asyncio
async def test_satusehat_encounter_maps_all_diagnoses_to_conditions(db_session, monkeypatch):
    monkeypatch.setattr(settings, "satusehat_mode", "sandbox", raising=False)
    monkeypatch.setattr(settings, "satusehat_org_id", "ORG-1", raising=False)
    monkeypatch.setattr(settings, "satusehat_location_id", "LOC-1", raising=False)

    tag = uuid.uuid4().hex[:8]
    src_pid = f"P-{tag}"
    ihs = "100000030009"

    src = sync.get_system(db_session, "openmrs")
    tgt = sync.get_system(db_session, "satusehat")
    db_session.add(IdentifierMapping(resource_type="Patient", source_system_id=src.id,
                                     target_system_id=tgt.id, source_identifier=src_pid,
                                     target_identifier=ihs, identifier_type="ihs",
                                     validation_status="verified"))
    db_session.commit()

    enc = {
        "resourceType": "Encounter", "status": "finished",
        "subject": {"reference": f"Patient/{src_pid}"},
        "reasonCode": [
            {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "J06.9", "display": "Acute URI"}]},
            {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "E11.9", "display": "Type 2 diabetes"}]},
        ],
    }
    job = SyncJob(resource_type="Encounter", source_system_id=src.id, target_system_id=tgt.id,
                  source_resource_id=f"enc-{tag}", idempotency_key=f"ss-enc-{tag}",
                  status="pending", payload_ref=json.dumps(enc))
    db_session.add(job)
    db_session.commit()

    fake = FakeSatusehat()
    orig = sync.get_adapter
    sync.get_adapter = lambda name: fake
    try:
        out = await sync.process_job(db_session, job)
        db_session.commit()
    finally:
        sync.get_adapter = orig

    assert out.status == "success", out.last_error
    bundle = fake.captured_bundle
    assert bundle is not None
    conditions = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Condition"]
    enc_res = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Encounter")
    assert len(conditions) == 2
    codes = [c["code"]["coding"][0]["code"] for c in conditions]
    assert codes == ["J06.9", "E11.9"]
    assert len(enc_res["diagnosis"]) == 2
