"""End-to-end tests via the running Management API + mocks (black-box).

Requires the stack running (docker compose up). Run inside the compose network:
    docker run --rm --network kapselrpld_default --env-file .env \
      -v "$PWD/backend:/app" -w /app kapselrpld-backend:latest \
      sh -c "pip install -q pytest pytest-asyncio && python -m pytest tests/e2e -q"
"""
import os
import time
import uuid

import httpx
import pytest

API = os.environ.get("API_BASE", "http://backend:8000")
MOCK_OPENEMR = os.environ.get("MOCK_OPENEMR", "http://mock-ehr:8100/openemr")
TOKEN = os.environ.get("ADMIN_API_TOKEN", "change_me_admin_token")
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def _enqueue(src, tgt, resource, version=""):
    r = httpx.post(f"{API}/api/v1/jobs/enqueue", headers=H,
                   json={"source_system": src, "target_system": tgt,
                         "resource": resource, "version": version}, timeout=20)
    r.raise_for_status()
    return r.json()["job_id"]


def _wait(job_id, timeout=40):
    end = time.time() + timeout
    while time.time() < end:
        r = httpx.get(f"{API}/api/v1/jobs/{job_id}", headers=H, timeout=20)
        j = r.json()
        if j["status"] in ("success", "failed_temp", "failed_perm", "needs_review", "conflict"):
            if j["status"] == "failed_temp" and time.time() < end:
                time.sleep(2)
                continue
            return j
        time.sleep(1.5)
    return {"status": "timeout"}


@pytest.mark.asyncio
async def test_health():
    r = httpx.get(f"{API}/health", timeout=10)
    assert r.status_code == 200 and r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_patient_sync_openmrs_to_openemr_e2e():
    mrn = f"E2E-{uuid.uuid4().hex[:8]}"
    patient = {"resourceType": "Patient",
               "identifier": [{"system": "http://openmrs.org/mrn", "value": mrn}],
               "name": [{"family": "E2E", "given": ["Test"]}], "gender": "male"}
    job_id = _enqueue("openmrs", "openemr", patient)
    j = _wait(job_id)
    assert j["status"] == "success", j
    # Verify it actually landed in OpenEMR mock
    r = httpx.get(f"{MOCK_OPENEMR}/Patient", params={"identifier": mrn}, timeout=15)
    assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_conflict_detection_e2e():
    mrn = f"CONF-{uuid.uuid4().hex[:8]}"
    base = {"resourceType": "Patient",
            "identifier": [{"system": "http://openmrs.org/mrn", "value": mrn}],
            "gender": "male"}
    j1 = _enqueue("openmrs", "openemr", {**base, "name": [{"family": "Asli"}]}, version="v1")
    assert _wait(j1)["status"] == "success"
    j2 = _enqueue("openmrs", "openemr", {**base, "name": [{"family": "Berubah"}]}, version="v2")
    assert _wait(j2)["status"] == "needs_review"
    # Conflict recorded
    r = httpx.get(f"{API}/api/v1/conflicts", headers=H, timeout=15)
    assert any(c["resource_type"] == "Patient" for c in r.json())
