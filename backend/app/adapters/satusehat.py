"""SATUSEHAT adapter.

Base path (sandbox): /fhir-r4/v1 . OAuth2 client_credentials. In mock mode the
mock-satusehat service enforces the profile/IHS rules. The adapter only performs
connectivity/auth/IO; validation decisions belong to the core.
"""
from __future__ import annotations

import httpx

from app.adapters.base import AdapterResult, make_error
from app.adapters.http_base import HttpFhirAdapter
from app.config import settings


class SatusehatAdapter(HttpFhirAdapter):
    name = "satusehat"

    def __init__(self) -> None:
        if settings.satusehat_mode == "mock":
            self.base_url = settings.satusehat_mock_url
        else:
            self.base_url = settings.satusehat_fhir_base_url
        self._token: str | None = None

    async def _ensure_token(self) -> None:
        if settings.satusehat_mode == "mock":
            self._token = "mock-token"
            return
        if self._token:
            return
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                settings.satusehat_token_url,
                data={"grant_type": "client_credentials",
                      "client_id": settings.satusehat_client_id,
                      "client_secret": settings.satusehat_client_secret},
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
                "auth", "Gagal memperoleh token SATUSEHAT", retryable=False, detail=str(exc)))
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

    async def inbound_search(self, resource_type: str, params: dict) -> AdapterResult:
        """Selective inbound read from SATUSEHAT (read-only)."""
        await self._ensure_token()
        return await self._request("GET", resource_type, params=params, headers=self._headers())

    async def get_raw(self, path: str, *, method: str = "GET", json: dict | None = None,
                      base: str | None = None) -> AdapterResult:
        """Raw call to an absolute path under a base (used by SSRME)."""
        await self._ensure_token()
        url = f"{(base or self.base_url).rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=40) as client:
                resp = await client.request(method, url, json=json, headers=self._headers())
        except httpx.HTTPError as exc:
            return AdapterResult(ok=False, error=make_error(
                "connectivity", "Gagal menghubungi SATUSEHAT", retryable=True, detail=str(exc)))
        if resp.status_code >= 400:
            cat = "validation" if resp.status_code in (400, 422) else (
                "auth" if resp.status_code in (401, 403) else "server")
            return AdapterResult(ok=False, http_status=resp.status_code, error=make_error(
                cat, f"Respons {resp.status_code}", retryable=resp.status_code >= 500,
                detail=resp.text[:1000]))
        body = resp.json() if resp.content else {}
        return AdapterResult(ok=True, http_status=resp.status_code, resource=body)

    async def transaction(self, bundle: dict) -> AdapterResult:
        """POST a FHIR transaction Bundle to the base URL (root, no resourceType).

        SATUSEHAT requires a transaction Bundle to create linked resources
        (e.g. Encounter + Condition) that reference each other via urn:uuid.
        """
        await self._ensure_token()
        url = self.base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=40) as client:
                resp = await client.post(url, json=bundle, headers=self._headers())
        except httpx.HTTPError as exc:
            return AdapterResult(ok=False, error=make_error(
                "connectivity", "Gagal mengirim transaction bundle", retryable=True, detail=str(exc)))
        if resp.status_code in (400, 422):
            return AdapterResult(ok=False, http_status=resp.status_code, error=make_error(
                "validation", "Bundle ditolak SATUSEHAT", retryable=False, detail=resp.text[:1500]))
        if resp.status_code >= 400:
            return AdapterResult(ok=False, http_status=resp.status_code, error=make_error(
                "server", f"Respons {resp.status_code}", retryable=resp.status_code >= 500,
                detail=resp.text[:800]))
        return AdapterResult(ok=True, http_status=resp.status_code, resource=resp.json())
