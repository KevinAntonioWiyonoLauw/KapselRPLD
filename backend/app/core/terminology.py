"""Terminology mapping (MVP: fixed table for 3-5 vital concepts).

Never auto-map clinical codes by assumption (proposal 2.5.7). If a concept is
not found, callers must flag the item for manual review instead of guessing.
"""
from __future__ import annotations

# concept_key -> {system_uri, code, display, unit}
DEFAULT_TERMINOLOGY: dict[str, dict] = {
    "body_temp": {"system": "http://loinc.org", "code": "8310-5",
                  "display": "Body temperature", "unit": "Cel"},
    "heart_rate": {"system": "http://loinc.org", "code": "8867-4",
                   "display": "Heart rate", "unit": "/min"},
    "body_weight": {"system": "http://loinc.org", "code": "29463-7",
                    "display": "Body weight", "unit": "kg"},
    "systolic_bp": {"system": "http://loinc.org", "code": "8480-6",
                    "display": "Systolic blood pressure", "unit": "mm[Hg]"},
    "diastolic_bp": {"system": "http://loinc.org", "code": "8462-4",
                     "display": "Diastolic blood pressure", "unit": "mm[Hg]"},
}


class TerminologyNotFound(Exception):
    pass


def lookup(concept_key: str) -> dict:
    if concept_key not in DEFAULT_TERMINOLOGY:
        raise TerminologyNotFound(f"Konsep '{concept_key}' tidak ada di tabel terminologi")
    return DEFAULT_TERMINOLOGY[concept_key]


def resolve_by_source_code(source_code: str) -> dict | None:
    """Map a raw source code (e.g. 'body_temp') to LOINC if it matches a key."""
    return DEFAULT_TERMINOLOGY.get(source_code)
