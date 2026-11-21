"""Unit tests: SATUSEHAT resource builder encodes mandatory rules."""
from app.core import satusehat_builder as b


def test_encounter_condition_bundle_has_mandatory_fields():
    bundle, enc_uuid = b.build_encounter_condition_bundle(
        org="ORG1", patient_ihs="100000030009", practitioner_ihs="10009880010",
        location_id="LOC1")
    assert bundle["type"] == "transaction"
    enc = bundle["entry"][0]["resource"]
    cond = bundle["entry"][1]["resource"]
    # Encounter mandatory (rules 10124/10457/10122)
    assert enc["serviceProvider"]["reference"] == "Organization/ORG1"
    assert enc["statusHistory"], "statusHistory wajib"
    assert enc["diagnosis"][0]["condition"]["reference"].startswith("urn:uuid:")
    assert enc["subject"]["reference"] == "Patient/100000030009"
    assert enc["diagnosis"][0]["use"]["coding"][0]["code"] == "DD"
    # Condition mandatory (rule 10126) -> references encounter via urn
    assert cond["encounter"]["reference"] == f"urn:uuid:{enc_uuid}"


def test_bundle_emits_one_condition_per_diagnosis():
    diagnoses = [("J06.9", "Acute URI"), ("E11.9", "Type 2 diabetes"), ("I10", "Essential hypertension")]
    bundle, enc_uuid = b.build_encounter_condition_bundle(
        org="ORG1", patient_ihs="100000030009", practitioner_ihs="10009880010",
        location_id="LOC1", diagnoses=diagnoses)
    conditions = [e for e in bundle["entry"] if e["resource"]["resourceType"] == "Condition"]
    enc = bundle["entry"][0]["resource"]
    assert len(conditions) == 3
    # Encounter.diagnosis references all three conditions (in order)
    assert len(enc["diagnosis"]) == 3
    codes = [c["resource"]["code"]["coding"][0]["code"] for c in conditions]
    assert codes == ["J06.9", "E11.9", "I10"]
    for c in conditions:
        assert c["resource"]["encounter"]["reference"] == f"urn:uuid:{enc_uuid}"
    refs = [d["condition"]["reference"] for d in enc["diagnosis"]]
    assert refs == [c["fullUrl"] for c in conditions]


def test_bundle_falls_back_to_default_when_no_diagnosis():
    bundle, _ = b.build_encounter_condition_bundle(
        org="ORG1", patient_ihs="P", practitioner_ihs="PR", location_id="LOC1",
        diagnoses=[])
    conditions = [e for e in bundle["entry"] if e["resource"]["resourceType"] == "Condition"]
    assert len(conditions) == 1  # never zero: SATUSEHAT requires a Condition


def test_observation_has_issued_and_loinc():
    obs = b.build_observation(patient_ihs="100000030009", practitioner_ihs="10009880010",
                              encounter_id="enc-1", loinc_code="8867-4",
                              loinc_display="Heart rate", value=78, unit_code="/min")
    assert obs["issued"], "Observation.issued wajib (rule 10296)"
    assert obs["encounter"]["reference"] == "Encounter/enc-1"
    assert obs["code"]["coding"][0]["system"] == "http://loinc.org"
    assert obs["subject"]["reference"] == "Patient/100000030009"
