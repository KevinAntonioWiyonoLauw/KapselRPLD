"""Unit tests: terminology and idempotency key."""
from app.core import terminology
from app.services.sync import idempotency_key


def test_terminology_known_concepts():
    for key in ["body_temp", "heart_rate", "body_weight", "systolic_bp", "diastolic_bp"]:
        assert terminology.lookup(key)["system"] == "http://loinc.org"


def test_terminology_unknown_raises():
    try:
        terminology.lookup("nope")
        assert False, "expected TerminologyNotFound"
    except terminology.TerminologyNotFound:
        pass


def test_idempotency_key_stable_and_target_specific():
    a = idempotency_key("openmrs", "openemr", "Patient", "MRN-001", "v1")
    b = idempotency_key("openmrs", "openemr", "Patient", "MRN-001", "v1")
    c = idempotency_key("openmrs", "satusehat", "Patient", "MRN-001", "v1")
    assert a == b            # deterministic
    assert a != c            # target matters
