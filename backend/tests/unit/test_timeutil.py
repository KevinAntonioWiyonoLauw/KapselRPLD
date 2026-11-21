"""Unit tests for FHIR `_lastUpdated` time normalization (issue #5)."""
from datetime import datetime, timedelta, timezone

from app.scheduler.timeutil import fhir_last_updated


def test_format_is_utc_z_suffix():
    now = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    got = fhir_last_updated(now, lookback_minutes=10, overlap_seconds=30)
    assert got == "2026-11-21T11:49:30Z"
    assert got.endswith("Z")
    assert "+00:00" not in got


def test_non_utc_input_is_converted_to_utc():
    # 19:00 at UTC+7 == 12:00 UTC
    now = datetime(2026, 11, 21, 19, 0, 0, tzinfo=timezone(timedelta(hours=7)))
    got = fhir_last_updated(now, lookback_minutes=10, overlap_seconds=0)
    assert got == "2026-11-21T11:50:00Z"


def test_naive_datetime_is_treated_as_utc():
    now = datetime(2026, 11, 21, 12, 0, 0)  # no tzinfo
    got = fhir_last_updated(now, lookback_minutes=5, overlap_seconds=0)
    assert got == "2026-11-21T11:55:00Z"


def test_overlap_window_increases_lookback():
    now = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    without_overlap = fhir_last_updated(now, lookback_minutes=10, overlap_seconds=0)
    with_overlap = fhir_last_updated(now, lookback_minutes=10, overlap_seconds=30)
    assert with_overlap < without_overlap
