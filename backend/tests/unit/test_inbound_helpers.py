"""Unit tests: inbound pull helpers (#11)."""
from app.services.inbound import _identity_value


def test_identity_value_prefers_identifier():
    assert _identity_value({"identifier": [{"value": "NIK-1"}]}) == "NIK-1"


def test_identity_value_falls_back_to_id():
    assert _identity_value({"id": "sat-123"}) == "sat-123"


def test_identity_value_none_when_empty():
    assert _identity_value({}) is None
