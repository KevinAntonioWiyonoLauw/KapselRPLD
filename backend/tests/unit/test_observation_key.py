"""Unit tests for the Observation idempotency key (issue #2)."""
from app.services.sync import _observation_key


def test_key_uses_subject_code_effective():
    obs = {
        "resourceType": "Observation",
        "status": "final",
        "subject": {"reference": "Patient/1"},
        "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
        "effectiveDateTime": "2026-01-01T00:00:00Z",
    }
    assert _observation_key(obs) == {
        "subject": "Patient/1",
        "code": "8867-4",
        "date": "2026-01-01T00:00:00Z",
    }


def test_key_falls_back_to_issued_when_no_effective():
    obs = {
        "resourceType": "Observation",
        "subject": {"reference": "Patient/2"},
        "code": {"coding": [{"code": "8310-5"}]},
        "issued": "2026-02-02T10:00:00Z",
    }
    assert _observation_key(obs)["date"] == "2026-02-02T10:00:00Z"


def test_key_omits_missing_fields():
    obs = {"resourceType": "Observation", "code": {"coding": [{"code": "1234-5"}]}}
    assert _observation_key(obs) == {"code": "1234-5"}


def test_search_params_openemr_observation_is_empty():
    # OpenEMR rejects the `subject` search param on Observation -> create-only.
    from app.services.sync import _search_params
    obs = {
        "resourceType": "Observation",
        "subject": {"reference": "Patient/1"},
        "code": {"coding": [{"code": "8867-4"}]},
        "effectiveDateTime": "2026-01-01T00:00:00Z",
    }
    assert _search_params(obs, "openemr") == {}
    # Other targets still use the business key.
    assert _search_params(obs, "openmrs") == {
        "subject": "Patient/1", "code": "8867-4", "date": "2026-01-01T00:00:00Z"}
