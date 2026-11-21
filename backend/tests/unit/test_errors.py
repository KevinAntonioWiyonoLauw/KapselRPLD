"""Unit tests for OperationOutcome normalization + sanitization (issue #4)."""
import json

from app.core.errors import error_message, sanitize, summarize_operation_outcome


def test_summarize_extracts_diagnostics_code_expression():
    body = json.dumps({
        "resourceType": "OperationOutcome",
        "issue": [{
            "severity": "error",
            "code": "required",
            "diagnostics": "Encounter.subject wajib",
            "expression": ["Encounter.subject"],
        }],
    })
    out = summarize_operation_outcome(body)
    assert "Encounter.subject wajib" in out
    assert "[required]" in out
    assert "Encounter.subject" in out


def test_summarize_multiple_issues_joined():
    body = json.dumps({"issue": [
        {"diagnostics": "field A salah", "code": "invalid"},
        {"details": {"text": "field B wajib"}, "code": "required"},
    ]})
    out = summarize_operation_outcome(body)
    assert "field A salah" in out and "field B wajib" in out
    assert " | " in out


def test_summarize_non_json_truncated_and_sanitized():
    out = summarize_operation_outcome("boom " * 500, limit=50)
    assert len(out) <= 50


def test_sanitize_masks_bearer_token():
    assert "***" in sanitize("Authorization: Bearer abc.def.ghi")
    assert "abc.def.ghi" not in sanitize("Authorization: Bearer abc.def.ghi")


def test_sanitize_masks_client_secret_json():
    out = sanitize('{"client_secret":"supersecret123","x":1}')
    assert "supersecret123" not in out
    assert "***" in out


def test_error_message_combines_and_truncates():
    msg = error_message("Data ditolak", "x" * 500)
    assert msg.startswith("Data ditolak: ")
    assert len(msg) <= len("Data ditolak: ") + 160


def test_error_message_label_only_when_no_detail():
    assert error_message("Data ditolak", "") == "Data ditolak"
