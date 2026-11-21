"""Unit tests: target-aware validation."""
from app.core import validation


def _satusehat_patient(ihs=True):
    ids = [{"system": "https://fhir.kemkes.go.id/id/ihs-number", "value": "1"}] if ihs else []
    return {"resourceType": "Patient", "identifier": ids}


def test_satusehat_patient_without_ihs_rejected():
    r = validation.validate_for_target(_satusehat_patient(ihs=False), "satusehat")
    assert not r.ok
    assert any("IHS" in i for i in r.issues)


def test_satusehat_patient_with_ihs_ok():
    r = validation.validate_for_target(_satusehat_patient(ihs=True), "satusehat")
    assert r.ok


def test_observation_requires_loinc_for_satusehat():
    obs = {"resourceType": "Observation", "status": "final",
           "code": {"text": "x"}, "subject": {"reference": "Patient/1"}}
    r = validation.validate_for_target(obs, "satusehat")
    assert not r.ok
    assert any("LOINC" in i for i in r.issues)


def test_observation_loinc_ok_for_satusehat():
    obs = {"resourceType": "Observation", "status": "final",
           "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5"}]},
           "subject": {"reference": "Patient/100000030009"}}
    r = validation.validate_for_target(obs, "satusehat")
    assert r.ok


def test_openmrs_encounter_requires_type():
    enc = {"resourceType": "Encounter", "status": "finished",
           "subject": {"reference": "Patient/1"}}
    r = validation.validate_for_target(enc, "openmrs")
    assert not r.ok
    assert any("type" in i for i in r.issues)
