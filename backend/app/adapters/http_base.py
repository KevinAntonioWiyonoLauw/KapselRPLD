"""Shared HTTP plumbing for FHIR adapters (HTTPX)."""
from __future__ import annotations

import httpx

from app.adapters.base import AdapterResult, make_error
from app.core.errors import error_message, summarize_operation_outcome


def summarize_error_body(text: str, limit: int = 800) -> str:
    """Normalize FHIR OperationOutcome / fault bodies into a concise message."""
    return summarize_operation_outcome(text, limit=limit)


class HttpFhirAdapter:
    """Common HTTP GET/POST/PUT + error normalization for FHIR endpoints."""

    name: str = "base"
    base_url: str = ""
    timeout: float = 20.0

    async def _request(self, method: str, path: str, *, json: dict | None = None,
                       params: dict | None = None, headers: dict | None = None) -> AdapterResult:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.request(method, url, json=json, params=params, headers=headers)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.NetworkError) as exc:
            return AdapterResult(ok=False, error=make_error(
                "connectivity", f"Tidak dapat terhubung ke {self.name}", retryable=True, detail=str(exc)))
        except httpx.HTTPError as exc:
            return AdapterResult(ok=False, error=make_error(
                "unknown", f"Kesalahan HTTP ke {self.name}", retryable=True, detail=str(exc)))

        status = resp.status_code
        if status in (401, 403):
            summ = summarize_error_body(resp.text)
            return AdapterResult(ok=False, http_status=status, error=make_error(
                "auth", error_message("Autentikasi/otorisasi ditolak", summ), retryable=False, detail=summ))
        if status == 404:
            summ = summarize_error_body(resp.text)
            return AdapterResult(ok=False, http_status=status, error=make_error(
                "not_found", error_message("Resource tidak ditemukan", summ), retryable=False, detail=summ))
        if status in (400, 422):
            summ = summarize_error_body(resp.text)
            return AdapterResult(ok=False, http_status=status, error=make_error(
                "validation", error_message("Data ditolak oleh server tujuan", summ), retryable=False, detail=summ))
        if status >= 500:
            summ = summarize_error_body(resp.text)
            return AdapterResult(ok=False, http_status=status, error=make_error(
                "server", error_message("Kesalahan server tujuan", summ), retryable=True, detail=summ))
        if status >= 400:
            summ = summarize_error_body(resp.text)
            return AdapterResult(ok=False, http_status=status, error=make_error(
                "unknown", error_message(f"Respons tak terduga ({status})", summ), retryable=False, detail=summ))

        body = resp.json() if resp.content else {}
        if body.get("resourceType") == "Bundle":
            return AdapterResult(ok=True, http_status=status, bundle=body)
        return AdapterResult(ok=True, http_status=status, resource=body,
                             meta={"created": status == 201})

    async def transaction(self, bundle: dict) -> AdapterResult:
        """Generic: POST a transaction Bundle to the base URL (no resourceType)."""
        url = self.base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=40) as client:
                resp = await client.request("POST", url, json=bundle)
        except httpx.HTTPError as exc:
            return AdapterResult(ok=False, error=make_error(
                "connectivity", f"Gagal transaction ke {self.name}", retryable=True, detail=str(exc)))
        if resp.status_code in (400, 422):
            return AdapterResult(ok=False, http_status=resp.status_code, error=make_error(
                "validation", "Bundle ditolak", retryable=False, detail=resp.text[:1500]))
        if resp.status_code >= 500:
            return AdapterResult(ok=False, http_status=resp.status_code, error=make_error(
                "server", "Kesalahan server", retryable=True, detail=resp.text[:800]))
        if resp.status_code >= 400:
            return AdapterResult(ok=False, http_status=resp.status_code, error=make_error(
                "unknown", f"Respons {resp.status_code}", retryable=False, detail=resp.text[:800]))
        return AdapterResult(ok=True, http_status=resp.status_code, resource=resp.json())
