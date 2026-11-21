"""Unit tests: FHIR transformation rules."""
from app.core import transform


def _patient():
    return {
        "resourceType": "Patient",
        "identifier": [{"system": "http://openmrs.org/mrn", "value": "MRN-001"}],
        "name": [{"family": "Santoso", "given": ["Budi"]}],
        "gender": "male",
    }


def test_patient_to_satusehat_adds_ihs_and_nik():
    out = transform.transform(_patient(), "satusehat",
                              {"ihs_number": "100000030009", "nik": "3400"})
    systems = {i["system"]: i["value"] for i in out["identifier"]}
    assert systems["https://fhir.kemkes.go.id/id/ihs-number"] == "100000030009"
    assert systems["https://fhir.kemkes.go.id/id/nik"] == "3400"


def test_encounter_to_openmrs_requires_type():
    enc = {"resourceType": "Encounter", "status": "finished",
           "subject": {"reference": "Patient/MRN-001"}}
    out = transform.transform(enc, "openmrs", {"patient_ref": "Patient/MRN-001"})
    coding = out["type"][0]["coding"][0]
    # FHIR2 only accepts encounter-type UUIDs via this system (verified live).
    assert coding["system"] == "http://fhir.openmrs.org/code-system/encounter-type"
    assert len(coding["code"]) == 36  # a UUID


def test_encounter_to_openmrs_overrides_type():
    # Any pre-existing type is replaced with a valid OpenMRS encounter-type UUID.
    enc = {"resourceType": "Encounter", "status": "finished",
           "type": [{"coding": [{"system": "http://fhir.openmrs.org/code-system/Encounter",
                                 "code": "VISIT"}]}],
           "subject": {"reference": "Patient/MRN-001"}}
    out = transform.transform(enc, "openmrs", {"patient_ref": "Patient/uuid-1"})
    coding = out["type"][0]["coding"][0]
    assert coding["system"] == "http://fhir.openmrs.org/code-system/encounter-type"
    assert out["subject"]["reference"] == "Patient/uuid-1"


def test_patient_to_openmrs_builds_preferred_identifier(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "openmrs_default_location_uuid", "loc-uuid", raising=False)
    out = transform.transform(_patient(), "openmrs", {})
    ident = out["identifier"][0]
    assert ident["use"] == "official"                       # preferred identifier
    assert ident["system"] == "http://openmrs.org/mrn"      # registered system
    assert ident["type"]["text"] == "Old Identification Number"  # resolvable type
    loc = [e for e in ident["extension"]
           if e["url"] == "http://fhir.openmrs.org/ext/patient/identifier#location"]
    assert loc and loc[0]["valueReference"]["reference"] == "Location/loc-uuid"


def test_encounter_subject_rewritten_to_mapped_ref():
    enc = {"resourceType": "Encounter", "status": "finished",
           "subject": {"reference": "Patient/MRN-001"}}
    out = transform.transform(enc, "openemr", {"patient_ref": "Patient/1"})
    assert out["subject"]["reference"] == "Patient/1"


def test_observation_code_mapped_to_loinc():
    obs = {"resourceType": "Observation", "status": "final",
           "code": {"text": "body_temp"}, "subject": {"reference": "Patient/MRN-001"},
           "valueQuantity": {"value": 36.8, "unit": "Cel"}}
    out = transform.transform(obs, "satusehat",
                              {"patient_ref": "Patient/100000030009"})
    coding = out["code"]["coding"][0]
    assert coding["system"] == "http://loinc.org"
    assert coding["code"] == "8310-5"
    assert out["valueQuantity"]["code"] == "Cel"
    assert out["subject"]["reference"] == "Patient/100000030009"


def test_observation_unknown_concept_not_mapped():
    obs = {"resourceType": "Observation", "status": "final",
           "code": {"text": "unknown_concept"}, "subject": {"reference": "Patient/MRN-001"}}
    out = transform.transform(obs, "satusehat", {})
    # Must NOT invent a LOINC code
    assert out["code"].get("text") == "unknown_concept"
    assert "coding" not in out["code"]


def test_patient_to_openemr_sets_official_name():
    out = transform.transform(_patient(), "openemr", {})
    assert out["name"][0]["use"] == "official"


def test_observation_to_openemr_adds_category():
    obs = {"resourceType": "Observation", "status": "final",
           "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
           "subject": {"reference": "Patient/1"}}
    out = transform.transform(obs, "openemr", {"patient_ref": "Patient/1"})
    assert out["category"][0]["coding"][0]["code"] == "vital-signs"
