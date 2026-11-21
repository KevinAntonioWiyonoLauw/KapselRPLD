"""OpenEMR adapter.

Base path: /apis/default/fhir . OAuth2 (client_credentials for server-to-server).
In mock mode a token is not required.
"""
from __future__ import annotations

import httpx

from app.adapters.base import AdapterResult, make_error
from app.adapters.http_base import HttpFhirAdapter
from app.config import settings


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
            resp = await client.post(
                settings.openemr_token_url,
                data={"grant_type": "client_credentials",
                      "client_id": settings.openemr_client_id,
                      "client_secret": settings.openemr_client_secret},
            )
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
        return await self._request("POST", resource_type, json=resource, headers=self._headers())

    async def update(self, resource_type: str, resource_id: str, resource: dict) -> AdapterResult:
        await self._ensure_token()
        return await self._request("PUT", f"{resource_type}/{resource_id}", json=resource,
                                   headers=self._headers())
