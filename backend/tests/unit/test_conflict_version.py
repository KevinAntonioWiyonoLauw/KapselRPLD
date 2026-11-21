"""Unit tests for version-based conflict classification (issue #1 / F4)."""
from app.core.conflict import classify_version_conflict


def _classify(src, tgt, base_src, base_tgt):
    return classify_version_conflict(
        source_version=src, target_version=tgt,
        baseline_source=base_src, baseline_target=base_tgt,
    )


def test_idempotent_when_nothing_changed():
    assert _classify("v1", "t1", "v1", "t1") == "idempotent"


def test_source_newer_when_only_source_changed():
    assert _classify("v2", "t1", "v1", "t1") == "source_newer"


def test_target_newer_when_only_target_changed():
    assert _classify("v1", "t2", "v1", "t1") == "target_newer"


def test_conflict_when_both_changed():
    assert _classify("v2", "t2", "v1", "t1") == "conflict"


def test_idempotent_when_no_baseline_but_equal():
    # Degenerate inputs still classify deterministically.
    assert _classify("v1", "v1", "v1", "v1") == "idempotent"
