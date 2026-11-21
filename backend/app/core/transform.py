"""FHIR transformation between systems.

Rules grounded in verified behaviour:
- OpenMRS Encounter requires Encounter.type (code system fhir.openmrs.org/...).
- OpenMRS Observation is append-only (create only).
- SATUSEHAT requires IHS references for Patient subject.
- Observation.code is mapped through the fixed terminology table (no guessing).
"""
from __future__ import annotations

import copy

from app.config import settings
from app.core import terminology

# OpenMRS FHIR2 code system URIs (verified against the reference application).
_OMRS_ENCOUNTER_TYPE_SYSTEM = "http://fhir.openmrs.org/code-system/encounter-type"
_OMRS_IDENTIFIER_LOCATION_EXT = "http://fhir.openmrs.org/ext/patient/identifier#location"


class TransformError(Exception):
    pass


def _rewrite_subject(resource: dict, ctx: dict) -> None:
    if ctx.get("patient_ref"):
        resource["subject"] = {"reference": ctx["patient_ref"]}
    if ctx.get("encounter_ref") and resource.get("resourceType") == "Observation":
        resource["encounter"] = {"reference": ctx["encounter_ref"]}


def _openmrs_identifier(identifier: dict) -> dict:
    """Normalise one Patient.identifier for OpenMRS FHIR2 create.

    FHIR2 requires: a preferred (use=official) identifier, a resolvable type
    (matched via ``type.text`` == OpenMRS identifier-type name), the registered
    ``identifier.system`` (see fhir_patient_identifier_system), and a location
    extension. Without these it rejects the create.
    """
    ident = dict(identifier)
    ident["use"] = "official"
    ident.setdefault("system", settings.openmrs_identifier_system)
    # FHIR2 resolves the identifier type from type.text (the OpenMRS type name).
    ident["type"] = {"text": settings.openmrs_identifier_type_name}
    if settings.openmrs_default_location_uuid:
        exts = [e for e in (ident.get("extension") or [])
                if e.get("url") != _OMRS_IDENTIFIER_LOCATION_EXT]
        exts.append({
            "url": _OMRS_IDENTIFIER_LOCATION_EXT,
            "valueReference": {"reference": f"Location/{settings.openmrs_default_location_uuid}"},
        })
        ident["extension"] = exts
    return ident


def transform_patient(resource: dict, target_system: str, ctx: dict) -> dict:
    out = copy.deepcopy(resource)
    # Ensure a stable local identifier exists
    out.setdefault("identifier", [])
    if target_system == "satusehat" and ctx.get("ihs_number"):
        out["identifier"] = [
            {"system": "https://fhir.kemkes.go.id/id/ihs-number",
             "value": ctx["ihs_number"]}
        ]
        if ctx.get("nik"):
            out["identifier"].append({"system": "https://fhir.kemkes.go.id/id/nik",
                                      "value": ctx["nik"]})
    # OpenMRS FHIR2 needs a preferred identifier (type + system + location).
    if target_system == "openmrs" and out.get("identifier"):
        out["identifier"] = [_openmrs_identifier(out["identifier"][0])]
    # OpenEMR maps only a name with use=official to first/last name fields.
    if target_system == "openemr" and out.get("name"):
        if not any((n or {}).get("use") == "official" for n in out["name"]):
            out["name"][0]["use"] = "official"
    return out


def transform_encounter(resource: dict, target_system: str, ctx: dict) -> dict:
    out = copy.deepcopy(resource)
    _rewrite_subject(out, ctx)
    # OpenMRS requires Encounter.type referencing an encounter-type UUID via the
    # fhir.openmrs.org/code-system/encounter-type system (verified: any other
    # coding is rejected with "Invalid type of request").
    if target_system == "openmrs":
        out["type"] = [{
            "coding": [{
                "system": _OMRS_ENCOUNTER_TYPE_SYSTEM,
                "code": settings.openmrs_encounter_type_uuid,
                "display": settings.openmrs_encounter_type_name,
            }]
        }]
    return out


def transform_observation(resource: dict, target_system: str, ctx: dict) -> dict:
    out = copy.deepcopy(resource)
    _rewrite_subject(out, ctx)
    # OpenEMR needs Observation.category to route the write to the right store.
    if target_system == "openemr" and not out.get("category"):
        out["category"] = [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "vital-signs",
                "display": "Vital Signs",
            }]
        }]
    # Map code to LOINC via fixed table when a known concept key is present.
    code = out.get("code", {})
    raw = None
    if isinstance(code.get("text"), str):
        raw = code["text"]
    elif code.get("coding"):
        raw = code["coding"][0].get("code")
    mapped = terminology.resolve_by_source_code(raw) if raw else None
    if mapped:
        out["code"] = {
            "coding": [{"system": mapped["system"], "code": mapped["code"],
                        "display": mapped["display"]}],
            "text": mapped["display"],
        }
        if out.get("valueQuantity") and mapped.get("unit"):
            out["valueQuantity"]["unit"] = mapped["unit"]
            out["valueQuantity"]["system"] = "http://unitsofmeasure.org"
            out["valueQuantity"]["code"] = mapped["unit"]
    return out


def transform(resource: dict, target_system: str, ctx: dict) -> dict:
    rtype = resource.get("resourceType")
    if rtype == "Patient":
        return transform_patient(resource, target_system, ctx)
    if rtype == "Encounter":
        return transform_encounter(resource, target_system, ctx)
    if rtype == "Observation":
        return transform_observation(resource, target_system, ctx)
    raise TransformError(f"Transformasi untuk resource {rtype} belum didukung")
