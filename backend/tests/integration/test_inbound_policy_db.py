"""DB integration test: policy-driven selective inbound from SATUSEHAT (#11).

Uses a fake SATUSEHAT (source) + fake target EHR adapter to verify:
- a policy pulls only resources matching its filter (search params passed through),
- each pulled resource is created in the target and an IdentifierMapping is stored,
- re-running is idempotent (no duplicate creates).
"""
import uuid

import pytest

from app.adapters.base import AdapterResult
from app.services import inbound, sync
from app.models import IdentifierMapping, SyncPolicy


class FakeSatusehatSource:
    def __init__(self, resources):
        self.resources = resources
        self.last_params = None

    async def search(self, rt, params):
        self.last_params = params
        return AdapterResult(ok=True, http_status=200, bundle={
            "resourceType": "Bundle", "total": len(self.resources),
            "entry": [{"resource": r} for r in self.resources]})


class FakeTarget:
    def __init__(self):
        self.created = []

    async def create(self, rt, resource):
        self.created.append(resource)
        return AdapterResult(ok=True, http_status=201,
                             resource={"resourceType": rt, "id": f"tgt-{len(self.created)}"})


@pytest.mark.asyncio
async def test_inbound_policy_pulls_and_is_idempotent(db_session):
    tag = uuid.uuid4().hex[:8]
    src = sync.get_system(db_session, "satusehat")
    tgt = sync.get_system(db_session, "openmrs")
    policy = SyncPolicy(source_system_id=src.id, target_system_id=tgt.id,
                        resource_type="Observation", direction="inbound",
                        enabled=True, filter_json={"category": "vital-signs"})
    db_session.add(policy)
    db_session.commit()

    resources = [
        {"resourceType": "Observation", "id": f"sat-obs-{tag}-1",
         "identifier": [{"value": f"SAT-{tag}-1"}], "status": "final"},
        {"resourceType": "Observation", "id": f"sat-obs-{tag}-2",
         "identifier": [{"value": f"SAT-{tag}-2"}], "status": "final"},
    ]
    fake_src = FakeSatusehatSource(resources)
    fake_tgt = FakeTarget()
    adapters = {"satusehat": fake_src, "openmrs": fake_tgt}
    orig = sync.get_adapter
    inbound.get_adapter = lambda name: adapters[name]
    try:
        r1 = await inbound.pull_policy(db_session, policy)
        db_session.commit()
        assert r1["ok"] and r1["pulled"] == 2 and r1["created"] == 2
        assert fake_src.last_params == {"category": "vital-signs"}  # filter passed through
        assert len(fake_tgt.created) == 2

        # re-run: idempotent, no new creates
        r2 = await inbound.pull_policy(db_session, policy)
        db_session.commit()
        assert r2["skipped"] == 2 and r2["created"] == 0
        assert len(fake_tgt.created) == 2

        # mappings stored for both
        rows = db_session.query(IdentifierMapping).filter(
            IdentifierMapping.source_system_id == src.id,
            IdentifierMapping.target_system_id == tgt.id,
            IdentifierMapping.resource_type == "Observation").all()
        assert len(rows) >= 2
    finally:
        inbound.get_adapter = orig
