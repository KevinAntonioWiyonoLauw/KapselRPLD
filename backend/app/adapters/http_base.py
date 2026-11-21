"""Shared HTTP plumbing for FHIR adapters (HTTPX)."""
from __future__ import annotations

import json

import httpx

from app.adapters.base import AdapterResult, make_error


def summarize_error_body(text: str, limit: int = 800) -> str:
    """Normalize FHIR OperationOutcome / fault bodies into a concise message."""
    if not text:
        return ""
    try:
        data = json.loads(text)
    except Exception:  # noqa: BLE001
        return text[:limit]
    msgs: list[str] = []
    for issue in data.get("issue", []) or []:
        txt = (issue.get("details") or {}).get("text") or issue.get("diagnostics")
        if txt:
            rule = issue.get("expression")
            msgs.append(f"{txt}" + (f" {rule}" if rule else ""))
    fault = data.get("fault")
    if fault:
        msgs.append(fault.get("faultstring", "fault"))
    if data.get("message"):
        msgs.append(str(data["message"]))
    return (" | ".join(msgs) or text)[:limit]


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
            return AdapterResult(ok=False, http_status=status, error=make_error(
                "auth", "Autentikasi/otorisasi ditolak", retryable=False, detail=summarize_error_body(resp.text)))
        if status == 404:
            return AdapterResult(ok=False, http_status=status, error=make_error(
                "not_found", "Resource tidak ditemukan", retryable=False, detail=summarize_error_body(resp.text)))
        if status in (400, 422):
            return AdapterResult(ok=False, http_status=status, error=make_error(
                "validation", "Data ditolak oleh server tujuan", retryable=False, detail=summarize_error_body(resp.text)))
        if status >= 500:
            return AdapterResult(ok=False, http_status=status, error=make_error(
                "server", "Kesalahan server tujuan", retryable=True, detail=summarize_error_body(resp.text)))
        if status >= 400:
            return AdapterResult(ok=False, http_status=status, error=make_error(
                "unknown", f"Respons tak terduga ({status})", retryable=False, detail=summarize_error_body(resp.text)))

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
