"""Build SATUSEHAT-compliant FHIR resources.

Encodes the mandatory-field rules discovered from real sandbox validation
(see docs/satusehat-integration.md §4). Encounter + Condition are emitted as a
transaction Bundle with urn:uuid references to satisfy the circular dependency.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.adapters.base import AdapterInterface
from app.config import settings


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


async def ensure_location(adapter: AdapterInterface, org: str) -> str | None:
    """Return an existing Location id for the org, or create one."""
    if settings.satusehat_location_id:
        return settings.satusehat_location_id
    res = await adapter.search("Location", {"organization": f"Organization/{org}"})
    if res.ok and res.bundle and res.bundle.get("total", 0) > 0:
        return res.bundle["entry"][0]["resource"]["id"]
    loc = {
        "resourceType": "Location",
        "identifier": [{"system": f"http://sys-ids.kemkes.go.id/location/{org}",
                        "value": f"LOC-{uuid.uuid4().hex[:6]}"}],
        "status": "active",
        "name": "Ruang Poli Umum",
        "managingOrganization": {"reference": f"Organization/{org}"},
    }
    created = await adapter.create("Location", loc)
    if created.ok and created.resource:
        return created.resource.get("id")
    return None


def build_encounter_condition_bundle(
    *, org: str, patient_ihs: str, practitioner_ihs: str, location_id: str,
    diagnoses: list[tuple[str, str]] | None = None,
    icd10: str | None = None, icd10_display: str | None = None,
) -> tuple[dict, str]:
    """Return (transaction_bundle, encounter_urn_uuid).

    ``diagnoses`` is an ordered list of (icd10_code, display). Every diagnosis
    becomes its own Condition resource; Encounter.diagnosis references each one.
    Falls back to the configured default diagnosis when the list is empty so the
    Encounter still carries at least one Condition (SATUSEHAT requires it).
    ``icd10``/``icd10_display`` are kept for backward compatibility.
    """
    if diagnoses is None:
        if icd10 or icd10_display:
            diagnoses = [(icd10 or settings.satusehat_default_icd10,
                          icd10_display or settings.satusehat_default_icd10_display)]
        else:
            diagnoses = [(settings.satusehat_default_icd10,
                          settings.satusehat_default_icd10_display)]
    if not diagnoses:
        diagnoses = [(settings.satusehat_default_icd10,
                      settings.satusehat_default_icd10_display)]

    enc_uuid = str(uuid.uuid4())
    start = now_iso()
    end = start
    enc_value = f"ENC-{uuid.uuid4().hex[:10]}"

    condition_entries: list[dict] = []
    diagnosis_refs: list[dict] = []
    for code, display in diagnoses:
        cond_uuid = str(uuid.uuid4())
        condition = {
            "resourceType": "Condition",
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                           "code": "active"}]},
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-category",
                                      "code": "encounter-diagnosis"}]}],
            "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": code,
                                 "display": display or code}]},
            "subject": {"reference": f"Patient/{patient_ihs}"},
            "encounter": {"reference": f"urn:uuid:{enc_uuid}"},
        }
        condition_entries.append({
            "fullUrl": f"urn:uuid:{cond_uuid}",
            "request": {"method": "POST", "url": "Condition"},
            "resource": condition,
        })
        diagnosis_refs.append({
            "condition": {"reference": f"urn:uuid:{cond_uuid}"},
            "use": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/diagnosis-role",
                                "code": "DD"}]},
        })

    encounter = {
        "resourceType": "Encounter", "status": "finished",
        "identifier": [{"system": f"http://sys-ids.kemkes.go.id/encounter/{org}", "value": enc_value}],
        "statusHistory": [
            {"status": "arrived", "period": {"start": start, "end": end}},
            {"status": "in-progress", "period": {"start": start, "end": end}},
            {"status": "finished", "period": {"start": start, "end": end}},
        ],
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                  "code": "AMB", "display": "ambulatory"},
        "subject": {"reference": f"Patient/{patient_ihs}"},
        "participant": [{
            "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                                  "code": "ATND"}]}],
            "individual": {"reference": f"Practitioner/{practitioner_ihs}"},
        }],
        "period": {"start": start, "end": end},
        "location": [{"location": {"reference": f"Location/{location_id}"}}],
        "serviceProvider": {"reference": f"Organization/{org}"},
        "diagnosis": diagnosis_refs,
    }
    bundle = {
        "resourceType": "Bundle", "type": "transaction",
        "entry": [
            {"fullUrl": f"urn:uuid:{enc_uuid}", "request": {"method": "POST", "url": "Encounter"},
             "resource": encounter},
            *condition_entries,
        ],
    }
    return bundle, enc_uuid


def build_observation(*, patient_ihs: str, practitioner_ihs: str, encounter_id: str,
                      loinc_code: str, loinc_display: str, value: float, unit_code: str,
                      effective: str | None = None) -> dict:
    ts = effective or now_iso()
    return {
        "resourceType": "Observation", "status": "final",
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                  "code": "vital-signs", "display": "Vital Signs"}]}],
        "code": {"coding": [{"system": "http://loinc.org", "code": loinc_code,
                             "display": loinc_display}]},
        "subject": {"reference": f"Patient/{patient_ihs}"},
        "encounter": {"reference": f"Encounter/{encounter_id}"},
        "performer": [{"reference": f"Practitioner/{practitioner_ihs}"}],
        "effectiveDateTime": ts,
        "issued": ts,
        "valueQuantity": {"value": value, "unit": unit_code,
                          "system": "http://unitsofmeasure.org", "code": unit_code},
    }
