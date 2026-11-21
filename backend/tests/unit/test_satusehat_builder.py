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


def test_observation_has_issued_and_loinc():
    obs = b.build_observation(patient_ihs="100000030009", practitioner_ihs="10009880010",
                              encounter_id="enc-1", loinc_code="8867-4",
                              loinc_display="Heart rate", value=78, unit_code="/min")
    assert obs["issued"], "Observation.issued wajib (rule 10296)"
    assert obs["encounter"]["reference"] == "Encounter/enc-1"
    assert obs["code"]["coding"][0]["system"] == "http://loinc.org"
    assert obs["subject"]["reference"] == "Patient/100000030009"
