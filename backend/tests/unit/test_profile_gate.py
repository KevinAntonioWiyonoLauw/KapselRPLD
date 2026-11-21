"""Unit tests: helpers for the SATUSEHAT profile-validation gate (#9)."""
from app.services.sync import _satusehat_bundle_resources


def test_bundle_resources_extracts_only_profile_resources():
    bundle = {"entry": [
        {"resource": {"resourceType": "Encounter"}},
        {"resource": {"resourceType": "Condition"}},  # skipped (referenced, not validated)
        {"resource": {"resourceType": "Observation"}},
    ]}
    types = [r["resourceType"] for r in _satusehat_bundle_resources(bundle)]
    assert types == ["Encounter", "Observation"]
