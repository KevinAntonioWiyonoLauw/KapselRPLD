"""Integration tests: adapters against running mock services (docker network).

Run inside the backend container so hostnames mock-ehr / mock-satusehat resolve:
    docker compose exec backend sh -c "pip install -q pytest pytest-asyncio && python -m pytest tests/integration -q"
"""
import pytest

from app.adapters.registry import get_adapter


@pytest.mark.asyncio
async def test_openmrs_capability():
    r = await get_adapter("openmrs").get_capability()
    assert r.ok and r.resource["resourceType"] == "CapabilityStatement"


@pytest.mark.asyncio
async def test_openemr_capability():
    r = await get_adapter("openemr").get_capability()
    assert r.ok and r.resource["resourceType"] == "CapabilityStatement"


@pytest.mark.asyncio
async def test_satusehat_capability():
    r = await get_adapter("satusehat").get_capability()
    assert r.ok and r.resource["resourceType"] == "CapabilityStatement"


@pytest.mark.asyncio
async def test_openmrs_search_patients_returns_bundle():
    r = await get_adapter("openmrs").search("Patient", {})
    assert r.ok and r.bundle["resourceType"] == "Bundle"


@pytest.mark.asyncio
async def test_satusehat_rejects_patient_without_ihs():
    adapter = get_adapter("satusehat")
    bad = {"resourceType": "Patient", "name": [{"text": "No IHS"}]}
    r = await adapter.create("Patient", bad)
    assert not r.ok
    assert r.error["category"] == "validation"
