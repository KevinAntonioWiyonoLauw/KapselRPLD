"""SSRME (SATUSEHAT Rekam Medis Elektronik) viewing integration.

Implements the CHLink -> Consent -> SHLink flow per Juknis SSRME V2.0:
- POST {ssrme_base}/chl  -> verificationUrl (pasien consent)
- POST {ssrme_base}/shl  -> shlinkUrl (nakes membuka RME nasional)
Body requires: patient_id (IHS), patient_name, practitioner_id (IHS),
practitioner_name, organization_id (IHS), organization_name.
"""
from __future__ import annotations

from app.adapters.satusehat import SatusehatAdapter
from app.config import settings


async def create_chlink(adapter: SatusehatAdapter, *, patient_id: str, patient_name: str,
                        practitioner_id: str, practitioner_name: str,
                        organization_id: str, organization_name: str) -> dict:
    body = {
        "patient_id": patient_id, "patient_name": patient_name,
        "practitioner_id": practitioner_id, "practitioner_name": practitioner_name,
        "organization_id": organization_id, "organization_name": organization_name,
    }
    res = await adapter.get_raw("chl", method="POST", json=body, base=settings.ssrme_base_url)
    return {"ok": res.ok, "http_status": res.http_status,
            "data": res.resource, "error": res.error}


async def create_shlink(adapter: SatusehatAdapter, *, patient_id: str, patient_name: str,
                        practitioner_id: str, practitioner_name: str,
                        organization_id: str, organization_name: str,
                        emergency: bool = False) -> dict:
    body = {
        "patient_id": patient_id, "patient_name": patient_name,
        "practitioner_id": practitioner_id, "practitioner_name": practitioner_name,
        "organization_id": organization_id, "organization_name": organization_name,
    }
    if emergency:
        body["type_medical_summary"] = "EMERGENCY"
    res = await adapter.get_raw("shl", method="POST", json=body, base=settings.ssrme_base_url)
    return {"ok": res.ok, "http_status": res.http_status,
            "data": res.resource, "error": res.error}
