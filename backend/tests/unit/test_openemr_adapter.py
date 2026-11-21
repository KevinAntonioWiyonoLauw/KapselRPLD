"""Unit tests for OpenEMR adapter create-response normalization (issue #7)."""
from app.adapters.base import AdapterResult
from app.adapters.openemr import OpenEMRAdapter


def _adapter():
    # Default config is mock mode; __init__ only sets base_url, no network.
    return OpenEMRAdapter()


def test_normalize_patient_uuid():
    res = _adapter()._normalize_create(
        "Patient", AdapterResult(ok=True, http_status=201, resource={"pid": 2, "uuid": "abc-123"}))
    assert res.ok
    assert res.resource["resourceType"] == "Patient"
    assert res.resource["id"] == "abc-123"
    assert res.resource["meta"]["lastUpdated"]


def test_normalize_encounter_euuid():
    res = _adapter()._normalize_create(
        "Encounter", AdapterResult(ok=True, http_status=201, resource={"eid": 5, "euuid": "enc-1"}))
    assert res.resource["id"] == "enc-1"


def test_normalize_observation_uuid():
    res = _adapter()._normalize_create(
        "Observation", AdapterResult(ok=True, http_status=201, resource={"uuid": "obs-9"}))
    assert res.resource["id"] == "obs-9"


def test_proper_fhir_resource_passes_through():
    original = AdapterResult(ok=True, http_status=201,
                             resource={"resourceType": "Patient", "id": "x"})
    res = _adapter()._normalize_create("Patient", original)
    assert res is original
    assert res.resource["id"] == "x"


def test_error_result_not_normalized():
    err = AdapterResult(ok=False, http_status=400, error={"category": "validation"})
    # create() only normalizes on ok; _normalize_create should not be called on errors,
    # but ensure it is a no-op-safe if it were.
    res = _adapter()._normalize_create("Patient", err)
    assert res.ok is False
