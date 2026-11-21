"""Validation: light structural checks + optional HAPI profile validation.

Light validator always runs (fast, no deps). HAPI validator is used when
USE_HAPI_VALIDATOR=true to validate against a target profile.
"""
from __future__ import annotations

import httpx

from app.config import settings

MANDATORY = {
    "Patient": ["resourceType"],
    "Encounter": ["resourceType", "status", "subject"],
    "Observation": ["resourceType", "status", "code", "subject"],
}


class ValidationResult:
    def __init__(self, ok: bool, issues: list[str] | None = None):
        self.ok = ok
        self.issues = issues or []


def light_validate(resource: dict) -> ValidationResult:
    issues: list[str] = []
    rtype = resource.get("resourceType")
    if not rtype:
        return ValidationResult(False, ["resourceType tidak ada"])
    for field in MANDATORY.get(rtype, ["resourceType"]):
        if field not in resource or resource.get(field) in (None, "", [], {}):
            issues.append(f"Elemen wajib '{field}' kosong pada {rtype}")
    # Reference sanity: subject must be a Reference object with 'reference'
    subj = resource.get("subject")
    if subj is not None and (not isinstance(subj, dict) or not subj.get("reference")):
        issues.append("Reference 'subject' tidak valid")
    return ValidationResult(len(issues) == 0, issues)


async def hapi_validate(resource: dict, profile_url: str | None = None) -> ValidationResult:
    """Validate via HAPI FHIR Validator (optional)."""
    if not settings.use_hapi_validator:
        return ValidationResult(True, [])
    payload = {"resource": resource}
    if profile_url:
        payload["profile"] = profile_url
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{settings.hapi_validator_url.rstrip('/')}/validate", json=payload)
        data = resp.json()
        issues = [i.get("message", "") for i in data.get("issue", []) if i.get("severity") in ("error", "fatal")]
        return ValidationResult(len(issues) == 0, issues)
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(False, [f"HAPI validator error: {exc}"])


async def validate(resource: dict, profile_url: str | None = None) -> ValidationResult:
    light = light_validate(resource)
    if not light.ok:
        return light
    return await hapi_validate(resource, profile_url)


SATUSEHAT_PROFILES = {
    "Patient": "https://fhir.kemkes.go.id/r4/StructureDefinition/Patient",
    "Encounter": "https://fhir.kemkes.go.id/r4/StructureDefinition/Encounter",
    "Observation": "https://fhir.kemkes.go.id/r4/StructureDefinition/Observation",
}


async def profile_validate(resource: dict, target_system: str) -> ValidationResult:
    """Full profile validation via HAPI (only when USE_HAPI_VALIDATOR=true)."""
    if not settings.use_hapi_validator:
        return ValidationResult(True, [])
    prof = SATUSEHAT_PROFILES.get(resource.get("resourceType")) if target_system == "satusehat" else None
    return await hapi_validate(resource, prof)


def _is_ihs_ref(ref: str) -> bool:
    return ref.startswith("Patient/") and ref.split("/")[-1].isdigit()


def validate_for_target(resource: dict, target_system: str) -> ValidationResult:
    """Target-aware validation of mandatory elements, references and terminology.

    Mirrors the rules the destination enforces (e.g. SATUSEHAT profile/IHS/LOINC)
    so the core rejects/queues invalid data BEFORE attempting delivery.
    """
    light = light_validate(resource)
    if not light.ok:
        return light

    issues: list[str] = []
    rtype = resource.get("resourceType")

    if target_system == "satusehat":
        if rtype == "Patient":
            ids = resource.get("identifier", [])
            if not any("ihs-number" in (i.get("system") or "") for i in ids):
                issues.append("Patient.identifier wajib memuat IHS number untuk SATUSEHAT")
        elif rtype == "Encounter":
            subj = (resource.get("subject") or {}).get("reference", "")
            if not _is_ihs_ref(subj):
                issues.append("Encounter.subject harus Patient/{patient-ihs-number}")
        elif rtype == "Observation":
            subj = (resource.get("subject") or {}).get("reference", "")
            if not _is_ihs_ref(subj):
                issues.append("Observation.subject harus Patient/{patient-ihs-number}")
            codings = (resource.get("code") or {}).get("coding", [])
            if not any(c.get("system") == "http://loinc.org" for c in codings):
                issues.append("Observation.code wajib memakai terminologi LOINC (tidak dapat dipetakan)")

    if target_system == "openmrs" and rtype == "Encounter":
        if not resource.get("type"):
            issues.append("Encounter.type wajib untuk OpenMRS")

    return ValidationResult(len(issues) == 0, issues)
