"""Unit tests: diagnosis extraction for the SATUSEHAT Condition mapping (#10)."""
from app.services.sync import _diagnoses_from_resource


def test_extracts_all_reason_codes():
    enc = {
        "resourceType": "Encounter",
        "reasonCode": [
            {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "J06.9", "display": "Acute URI"}]},
            {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "E11.9", "display": "Type 2 diabetes"}]},
        ],
    }
    assert _diagnoses_from_resource(enc) == [("J06.9", "Acute URI"), ("E11.9", "Type 2 diabetes")]


def test_supports_structured_diagnoses_list():
    enc = {"diagnoses": [{"code": "I10", "display": "Hypertension"}, ["J45.9", "Asthma"]]}
    assert _diagnoses_from_resource(enc) == [("I10", "Hypertension"), ("J45.9", "Asthma")]


def test_supports_single_custom_fields():
    enc = {"diagnosis_code": "A09", "diagnosis_display": "Diarrhoea"}
    assert _diagnoses_from_resource(enc) == [("A09", "Diarrhoea")]


def test_dedupes_and_ignores_non_icd10():
    enc = {
        "reasonCode": [
            {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "J06.9"}]},
            {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "J06.9"}]},
            {"coding": [{"system": "http://snomed.info/sct", "code": "123"}]},
        ],
    }
    assert _diagnoses_from_resource(enc) == [("J06.9", "J06.9")]


def test_empty_when_no_diagnosis():
    assert _diagnoses_from_resource({"resourceType": "Encounter"}) == []
