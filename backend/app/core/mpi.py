"""Master Patient Index (MPI) helpers for SATUSEHAT.

Resolve a patient's IHS number from a NIK via GET /Patient?identifier=nik|NIK.
See docs/satusehat-integration.md §MPI.
"""
from __future__ import annotations

from app.adapters.base import AdapterInterface

NIK_SYSTEM = "https://fhir.kemkes.go.id/id/nik"
IHS_SYSTEM = "https://fhir.kemkes.go.id/id/ihs-number"


def _ihs_from_patient(patient: dict) -> str | None:
    # The logical id of a SATUSEHAT Patient resource IS the IHS number.
    if patient.get("id"):
        return patient["id"]
    for ident in patient.get("identifier", []):
        if ident.get("system") == IHS_SYSTEM:
            return ident.get("value")
    return None


async def resolve_ihs_by_nik(adapter: AdapterInterface, nik: str) -> str | None:
    """Return the IHS number for a NIK, or None if not found in MPI."""
    result = await adapter.search("Patient", {"identifier": f"{NIK_SYSTEM}|{nik}"})
    if not result.ok or not result.bundle:
        return None
    for entry in result.bundle.get("entry", []):
        ihs = _ihs_from_patient(entry.get("resource", {}))
        if ihs:
            return ihs
    return None
