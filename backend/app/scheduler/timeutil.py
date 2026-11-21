"""Time helpers for FHIR polling.

`_lastUpdated` is normalized to UTC ISO-8601 with a `Z` suffix, which the FHIR
search parameter accepts across OpenMRS / OpenEMR / SATUSEHAT. A small overlap
window is applied so changes at the boundary are not missed (extra results are
harmless thanks to idempotency + search-before-create).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _as_utc(dt: datetime) -> datetime:
    """Return an aware UTC datetime. Naive datetimes are treated as UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fhir_last_updated(
    now: datetime | None = None,
    lookback_minutes: int = 10,
    overlap_seconds: int = 30,
) -> str:
    """Return a FHIR `_lastUpdated` lower bound as UTC ISO-8601 with `Z`.

    The value is `now - lookback - overlap`, so the poller fetches slightly more
    than strictly needed (deduped downstream) instead of risking a missed update.
    """
    current = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    start = current - timedelta(minutes=lookback_minutes, seconds=overlap_seconds)
    return start.strftime("%Y-%m-%dT%H:%M:%SZ")
