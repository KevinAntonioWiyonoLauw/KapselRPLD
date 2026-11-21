"""DB integration tests: HAPI profile-validation gate before SATUSEHAT delivery (#9).

When USE_HAPI_VALIDATOR=true, the pipeline must validate the payload against the
SATUSEHAT profile BEFORE sending. Invalid payloads go to needs_review and nothing
is sent; valid payloads pass through to the adapter.
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
        self.sent = False

    async def read(self, rt, rid):
        return AdapterResult(ok=True, http_status=200, resource={"resourceType": rt, "id": rid})

    async def search(self, rt, params):
        return AdapterResult(ok=True, http_status=200,
                             bundle={"resourceType": "Bundle", "total": 0, "entry": []})

    async def create(self, rt, resource):
        self.sent = True
        return AdapterResult(ok=True, http_status=201, resource={"resourceType": rt, "id": "x"})

    async def transaction(self, bundle):
        self.sent = True
        return AdapterResult(ok=True, http_status=200, resource={
            "resourceType": "Bundle", "type": "transaction-response",
            "entry": [{"response": {"location": "Encounter/enc-1"}}]})


class StubValidation:
    def __init__(self, ok: bool, issues=None):
        self._ok = ok
        self._issues = issues or []

    async def profile_validate(self, resource, target_system):
        class R:
            pass
        r = R(); r.ok = self._ok; r.issues = self._issues
        return r


def _make_encounter_job(db, ihs):
    tag = uuid.uuid4().hex[:8]
    src = sync.get_system(db, "openmrs")
    tgt = sync.get_system(db, "satusehat")
    src_pid = f"P-{tag}"
    db.add(IdentifierMapping(resource_type="Patient", source_system_id=src.id,
                             target_system_id=tgt.id, source_identifier=src_pid,
                             target_identifier=ihs, identifier_type="ihs",
                             validation_status="verified"))
    db.commit()
    enc = {"resourceType": "Encounter", "status": "finished",
           "subject": {"reference": f"Patient/{src_pid}"},
           "reasonCode": [{"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "J06.9"}]}]}
    job = SyncJob(resource_type="Encounter", source_system_id=src.id, target_system_id=tgt.id,
                  source_resource_id=f"enc-{tag}", idempotency_key=f"hapi-{tag}",
                  status="pending", payload_ref=json.dumps(enc))
    db.add(job)
    db.commit()
    return job


@pytest.mark.asyncio
async def test_invalid_payload_goes_to_needs_review_before_send(db_session, monkeypatch):
    monkeypatch.setattr(settings, "satusehat_mode", "sandbox", raising=False)
    monkeypatch.setattr(settings, "satusehat_org_id", "ORG-1", raising=False)
    monkeypatch.setattr(settings, "satusehat_location_id", "LOC-1", raising=False)
    monkeypatch.setattr(settings, "use_hapi_validator", True, raising=False)
    monkeypatch.setattr(sync.validation, "profile_validate",
                        lambda res, tgt: StubValidation(False, ["Encounter.serviceProvider wajib"]).profile_validate(res, tgt))

    job = _make_encounter_job(db_session, "100000030009")
    fake = FakeSatusehat()
    orig = sync.get_adapter
    sync.get_adapter = lambda name: fake
    try:
        out = await sync.process_job(db_session, job)
        db_session.commit()
    finally:
        sync.get_adapter = orig

    assert out.status == "needs_review"
    assert "Validasi profil" in (out.last_error or "")
    assert fake.sent is False  # nothing delivered


@pytest.mark.asyncio
async def test_valid_payload_is_delivered(db_session, monkeypatch):
    monkeypatch.setattr(settings, "satusehat_mode", "sandbox", raising=False)
    monkeypatch.setattr(settings, "satusehat_org_id", "ORG-1", raising=False)
    monkeypatch.setattr(settings, "satusehat_location_id", "LOC-1", raising=False)
    monkeypatch.setattr(settings, "use_hapi_validator", True, raising=False)
    monkeypatch.setattr(sync.validation, "profile_validate",
                        lambda res, tgt: StubValidation(True).profile_validate(res, tgt))

    job = _make_encounter_job(db_session, "100000030009")
    fake = FakeSatusehat()
    orig = sync.get_adapter
    sync.get_adapter = lambda name: fake
    try:
        out = await sync.process_job(db_session, job)
        db_session.commit()
    finally:
        sync.get_adapter = orig

    assert out.status == "success", out.last_error
    assert fake.sent is True
