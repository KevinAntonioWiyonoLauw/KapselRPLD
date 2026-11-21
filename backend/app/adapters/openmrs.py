"""OpenMRS adapter.

Base path: /ws/fhir2/R4 . Basic auth (default). Observation is append-only in
OpenMRS: update() returns a non-retryable validation error. Creating an Encounter
requires Encounter.type (handled in the transformer).
"""
from __future__ import annotations

import httpx

from app.adapters.base import AdapterResult, make_error
from app.adapters.http_base import HttpFhirAdapter
from app.config import settings


class OpenMRSAdapter(HttpFhirAdapter):
    name = "openmrs"

    def __init__(self) -> None:
        if settings.openmrs_mode == "mock":
            self.base_url = settings.openmrs_mock_url
        else:
            self.base_url = settings.openmrs_fhir_base_url
        self._auth = settings.openmrs_auth_type
        self._user = settings.openmrs_username
        self._pw = settings.openmrs_password

    def _headers(self) -> dict:
        base = {"Accept": "application/fhir+json", "Content-Type": "application/fhir+json"}
        if self._auth == "basic":
            import base64
            token = base64.b64encode(f"{self._user}:{self._pw}".encode()).decode()
            base["Authorization"] = f"Basic {token}"
        return base

    async def check_connectivity(self) -> AdapterResult:
        return await self.get_capability()

    async def get_capability(self) -> AdapterResult:
        return await self._request("GET", "metadata", headers=self._headers())

    async def read(self, resource_type: str, resource_id: str) -> AdapterResult:
        return await self._request("GET", f"{resource_type}/{resource_id}", headers=self._headers())

    async def search(self, resource_type: str, params: dict) -> AdapterResult:
        return await self._request("GET", resource_type, params=params, headers=self._headers())

    async def create(self, resource_type: str, resource: dict) -> AdapterResult:
        return await self._request("POST", resource_type, json=resource, headers=self._headers())

    async def update(self, resource_type: str, resource_id: str, resource: dict) -> AdapterResult:
        if resource_type == "Observation":
            return AdapterResult(ok=False, error=make_error(
                "validation",
                "OpenMRS Observation bersifat append-only (tidak mendukung update).",
                retryable=False))
        return await self._request("PUT", f"{resource_type}/{resource_id}", json=resource,
                                   headers=self._headers())
