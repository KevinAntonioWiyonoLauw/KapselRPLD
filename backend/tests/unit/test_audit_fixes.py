"""Regression tests (pure) for audit fix F3 — identifier priority by system."""
from app.services import sync


def test_f3_identifier_priority_system_over_position():
    res = {
        "resourceType": "Patient",
        "identifier": [
            {"system": "https://fhir.kemkes.go.id/id/nik", "value": "NIK123"},
            {"system": "http://openmrs.org/mrn", "value": "MRN777"},
        ],
    }
    assert sync._identifier_value(res) == "NIK123"


def test_f3_ihs_highest_priority():
    res = {
        "resourceType": "Patient",
        "identifier": [
            {"system": "http://openmrs.org/mrn", "value": "MRN1"},
            {"system": "https://fhir.kemkes.go.id/id/ihs-number", "value": "IHS999"},
        ],
    }
    assert sync._identifier_value(res) == "IHS999"


def test_f3_fallback_first_when_unknown_system():
    res = {"resourceType": "Patient", "identifier": [{"system": "x", "value": "V1"}, {"system": "y", "value": "V2"}]}
    assert sync._identifier_value(res) == "V1"


def test_f7_observation_search_params_include_date():
    obs = {"resourceType": "Observation", "status": "final",
           "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5"}]},
           "subject": {"reference": "Patient/1"},
           "effectiveDateTime": "2026-01-10T00:00:00+00:00"}
    params = sync._search_params(obs)
    assert params.get("date") == "2026-01-10T00:00:00+00:00"
    assert params.get("code") == "8310-5"


def test_diagnoses_from_resource_variants():
    assert sync._diagnoses_from_resource({"diagnosis_code": "A09"}) == [("A09", "A09")]
    r = {"reasonCode": [{"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "J06.9", "display": "URI"}]}]}
    assert sync._diagnoses_from_resource(r) == [("J06.9", "URI")]
    assert sync._diagnoses_from_resource({}) == []
