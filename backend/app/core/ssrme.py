"""SSRME (SATUSEHAT Rekam Medis Elektronik) viewing integration.

Implements the CHLink -> Consent -> SHLink flow per Juknis SSRME V2.0:
- POST {ssrme_base}/chl  -> verificationUrl (pasien consent)
- POST {ssrme_base}/shl  -> shlinkUrl (nakes membuka RME nasional)
Body requires: patient_id (IHS), patient_name, practitioner_id (IHS),
practitioner_name, organization_id (IHS), organization_name.

In mock mode the calls go to the mock server so the dashboard flow is demoable
without real credentials.
"""
from __future__ import annotations

import uuid

from app.adapters.satusehat import SatusehatAdapter
from app.config import settings


def _base() -> str:
    if settings.satusehat_mode == "mock":
        return settings.ssrme_mock_base_url
    return settings.ssrme_base_url


def _extract_urls(data: dict) -> dict:
    """Pull the patient-consent URL and the RME-open URL out of the raw response."""
    data = data or {}
    verification = (data.get("verificationUrl") or data.get("verification_url")
                    or data.get("url") or data.get("chl_url"))
    shlink = (data.get("shlinkUrl") or data.get("shlink_url")
              or data.get("shl_url") or data.get("url"))
    return {"verification_url": verification, "shlink_url": shlink}


async def create_chlink(adapter: SatusehatAdapter, *, patient_id: str, patient_name: str,
                        practitioner_id: str, practitioner_name: str,
                        organization_id: str, organization_name: str) -> dict:
    body = {
        "patient_id": patient_id, "patient_name": patient_name,
        "practitioner_id": practitioner_id, "practitioner_name": practitioner_name,
        "organization_id": organization_id, "organization_name": organization_name,
    }
    res = await adapter.get_raw("chl", method="POST", json=body, base=_base())
    return {"ok": res.ok, "http_status": res.http_status, "kind": "chlink",
            "data": res.resource, "error": res.error, **_extract_urls(res.resource or {})}


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
    res = await adapter.get_raw("shl", method="POST", json=body, base=_base())
    return {"ok": res.ok, "http_status": res.http_status, "kind": "shlink",
            "emergency": emergency, "data": res.resource, "error": res.error,
            **_extract_urls(res.resource or {})}
