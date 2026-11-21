"""OpenEMR adapter.

Base path: ``/apis/default/fhir``. OAuth2 (SMART-on-FHIR). Two token flows:

- **password grant** (``OPENEMR_USERNAME``/``OPENEMR_PASSWORD`` set): simplest for
  a local/real OpenEMR instance. Requires the ``oauth_password_grant`` global on.
- **client_credentials** (``OPENEMR_CLIENT_ID``/``OPENEMR_CLIENT_SECRET``): standard
  for a system client. Note: OpenEMR may require a JWT client assertion (asymmetric)
  for this grant, depending on the client registration.

In mock mode no token is required.

OpenEMR's FHIR ``create`` does not return a standard FHIR resource; it returns a
compact object (e.g. ``{"pid":2,"uuid":"..."}`` or ``{"eid":2,"euuid":"..."}``).
``create`` normalizes that into a minimal FHIR-shaped resource so the rest of the
pipeline can read ``id`` / ``meta.lastUpdated``.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.adapters.base import AdapterResult, make_error
from app.adapters.http_base import HttpFhirAdapter
from app.config import settings

# OpenEMR create response key -> the FHIR id field to expose.
_CREATE_ID_KEYS = {
    "Patient": "uuid",
    "Encounter": "euuid",
    "Observation": "uuid",
    "Condition": "uuid",
    "Practitioner": "uuid",
    "Location": "uuid",
}


class OpenEMRAdapter(HttpFhirAdapter):
    name = "openemr"

    def __init__(self) -> None:
        if settings.openemr_mode == "mock":
            self.base_url = settings.openemr_mock_url
        else:
            self.base_url = settings.openemr_fhir_base_url
        self._token: str | None = None

    async def _ensure_token(self) -> None:
        if settings.openemr_mode == "mock":
            self._token = "mock-token"
            return
        if self._token:
            return
        async with httpx.AsyncClient(timeout=20) as client:
            if settings.openemr_username:
                data = {
                    "grant_type": "password",
                    "client_id": settings.openemr_client_id,
                    "client_secret": settings.openemr_client_secret,
                    "username": settings.openemr_username,
                    "password": settings.openemr_password,
                    "user_role": "users",
                    "scope": "openid api:fhir api:oemr "
                             "user/Patient.read user/Patient.write "
                             "user/Encounter.read user/Encounter.write "
                             "user/Observation.read user/Observation.write",
                }
            else:
                data = {
                    "grant_type": "client_credentials",
                    "client_id": settings.openemr_client_id,
                    "client_secret": settings.openemr_client_secret,
                    "scope": "system/Patient.read system/Patient.write "
                             "system/Encounter.read system/Encounter.write "
                             "system/Observation.read system/Observation.write",
                }
            resp = await client.post(settings.openemr_token_url, data=data)
            resp.raise_for_status()
            self._token = resp.json()["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/fhir+json"}

    async def check_connectivity(self) -> AdapterResult:
        return await self.get_capability()

    async def get_capability(self) -> AdapterResult:
        try:
            await self._ensure_token()
        except Exception as exc:  # noqa: BLE001
            return AdapterResult(ok=False, error=make_error(
                "auth", "Gagal memperoleh token OpenEMR", retryable=False, detail=str(exc)))
        return await self._request("GET", "metadata", headers=self._headers())

    async def read(self, resource_type: str, resource_id: str) -> AdapterResult:
        await self._ensure_token()
        return await self._request("GET", f"{resource_type}/{resource_id}", headers=self._headers())

    async def search(self, resource_type: str, params: dict) -> AdapterResult:
        await self._ensure_token()
        return await self._request("GET", resource_type, params=params, headers=self._headers())

    async def create(self, resource_type: str, resource: dict) -> AdapterResult:
        await self._ensure_token()
        res = await self._request("POST", resource_type, json=resource, headers=self._headers())
        if not res.ok:
            return res
        return self._normalize_create(resource_type, res)

    async def update(self, resource_type: str, resource_id: str, resource: dict) -> AdapterResult:
        await self._ensure_token()
        res = await self._request("PUT", f"{resource_type}/{resource_id}", json=resource,
                                  headers=self._headers())
        if not res.ok:
            return res
        return self._normalize_create(resource_type, res)

    def _normalize_create(self, resource_type: str, res: AdapterResult) -> AdapterResult:
        """Turn OpenEMR's compact create response into a minimal FHIR resource."""
        body = res.resource or {}
        # Already a proper FHIR resource (mock or future versions): leave as-is.
        if body.get("resourceType"):
            return res
        id_key = _CREATE_ID_KEYS.get(resource_type, "uuid")
        rid = body.get(id_key) or body.get("uuid") or body.get("id")
        if not rid:
            return res
        normalized = {
            "resourceType": resource_type,
            "id": str(rid),
            "meta": {"lastUpdated": datetime.now(timezone.utc).isoformat()},
            "_openemr": body,  # keep raw payload for debugging (not used downstream)
        }
        return AdapterResult(ok=True, http_status=res.http_status, resource=normalized,
                             meta={**res.meta, "created": True})
