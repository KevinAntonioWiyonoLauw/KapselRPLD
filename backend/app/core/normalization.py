"""Normalization: validate basic FHIR structure and pass through to internal form.

The internal form is a thin dict wrapper so downstream stages stay decoupled from
raw HTTP responses.
"""
from __future__ import annotations

REQUIRED_FIELDS = {
    "Patient": ["resourceType"],
    "Encounter": ["resourceType", "status", "subject"],
    "Observation": ["resourceType", "status", "code"],
}


class NormalizationError(Exception):
    pass


def normalize(resource: dict) -> dict:
    if not isinstance(resource, dict):
        raise NormalizationError("Resource bukan objek JSON")
    rtype = resource.get("resourceType")
    if not rtype:
        raise NormalizationError("Elemen resourceType tidak ada")
    for field in REQUIRED_FIELDS.get(rtype, ["resourceType"]):
        if field not in resource:
            raise NormalizationError(f"Elemen wajib '{field}' tidak ada pada {rtype}")
    return {"resourceType": rtype, "resource": resource}
