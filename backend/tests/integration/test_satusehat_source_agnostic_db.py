"""Regression: SATUSEHAT pipeline is SOURCE-AGNOSTIC (adapter hub).

The adapter hub must route ANY EHR -> SATUSEHAT, not only OpenMRS. Historically
seed.py only created ``openmrs -> satusehat`` identity mappings, so an
``openemr -> satusehat`` job failed with "Identity mapping belum terverifikasi".
These tests lock in the fix:
1. seed provides an ``openemr -> satusehat`` verified mapping, and
2. an OpenEMR->SATUSEHAT Patient job resolves the IHS via that mapping and succeeds.
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
        self.read_calls = []

    async def read(self, rt, rid):
        self.read_calls.append((rt, rid))
        return AdapterResult(ok=True, http_status=200, resource={"resourceType": rt, "id": rid})

    async def search(self, rt, params):
        return AdapterResult(ok=True, http_status=200,
                             bundle={"resourceType": "Bundle", "total": 0, "entry": []})

    async def create(self, rt, resource):
        return AdapterResult(ok=True, http_status=201, resource={"resourceType": rt, "id": "x"})

    async def transaction(self, bundle):
        return AdapterResult(ok=True, http_status=200,
                             resource={"resourceType": "Bundle", "entry": []})


def _openemr_patient_job(db, ihs):
    tag = uuid.uuid4().hex[:8]
    src = sync.get_system(db, "openemr")
    tgt = sync.get_system(db, "satusehat")
    mrn = f"MRN-{tag}"
    # Verified openemr -> satusehat identity mapping (the exact gap fixed in seed).
    db.add(IdentifierMapping(resource_type="Patient", source_system_id=src.id,
                             target_system_id=tgt.id, source_identifier=mrn,
                             target_identifier=ihs, identifier_type="ihs",
                             validation_status="verified"))
    db.commit()
    patient = {"resourceType": "Patient",
               "identifier": [{"system": "http://openmrs.org/mrn", "value": mrn}],
               "name": [{"text": "Budi Santoso"}]}
    job = SyncJob(resource_type="Patient", source_system_id=src.id, target_system_id=tgt.id,
                  source_resource_id=mrn, idempotency_key=f"oe-ss-{tag}",
                  status="pending", payload_ref=json.dumps(patient))
    db.add(job)
    db.commit()
    return job, mrn, ihs


@pytest.mark.asyncio
async def test_openemr_to_satusehat_patient_resolves_ihs_and_succeeds(db_session, monkeypatch):
    monkeypatch.setattr(settings, "satusehat_mode", "sandbox", raising=False)
    monkeypatch.setattr(settings, "satusehat_org_id", "ORG-1", raising=False)

    job, mrn, ihs = _openemr_patient_job(db_session, "100000030009")
    fake = FakeSatusehat()
    orig = sync.get_adapter
    sync.get_adapter = lambda name: fake
    try:
        out = await sync.process_job(db_session, job)
        db_session.commit()
    finally:
        sync.get_adapter = orig

    assert out.status == "success", out.last_error
    # IHS resolved from the openemr->satusehat mapping (not the raw MRN).
    assert ("Patient", ihs) in fake.read_calls


@pytest.mark.asyncio
async def test_seed_provides_openemr_to_satusehat_mapping(db_session):
    import seed  # top-level module backend/seed.py

    openmrs = sync.get_system(db_session, "openmrs")
    openemr = sync.get_system(db_session, "openemr")
    satusehat = sync.get_system(db_session, "satusehat")
    seed.seed_mappings(db_session, openmrs, openemr, satusehat)
    db_session.commit()

    m = sync.identity.resolve(db_session, resource_type="Patient",
                              source_system_id=openemr.id,
                              target_system_id=satusehat.id,
                              source_identifier="MRN-001")
    assert m is not None
    assert m.target_identifier == "100000030009"
