"""Unit tests: SSRME URL extraction (#12)."""
from app.core.ssrme import _extract_urls


def test_extracts_camel_case_urls():
    assert _extract_urls({"verificationUrl": "https://a/chl"})["verification_url"] == "https://a/chl"
    assert _extract_urls({"shlinkUrl": "https://a/shl"})["shlink_url"] == "https://a/shl"


def test_extracts_snake_case_urls():
    out = _extract_urls({"verification_url": "u1", "shlink_url": "u2"})
    assert out["verification_url"] == "u1" and out["shlink_url"] == "u2"


def test_empty_when_absent():
    out = _extract_urls({})
    assert out["verification_url"] is None and out["shlink_url"] is None
