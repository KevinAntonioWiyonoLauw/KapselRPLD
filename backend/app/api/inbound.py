"""Selective inbound from SATUSEHAT (read-only), per Batasan #6."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.adapters.registry import get_adapter
from app.api.deps import require_operator

router = APIRouter(prefix="/satusehat", tags=["inbound"])


@router.get("/inbound/{resource_type}")
async def inbound(resource_type: str, request: Request, _: str = Depends(require_operator)):
    """Selectively read resources from SATUSEHAT using query params.

    Example: GET /api/v1/satusehat/inbound/Patient?identifier=<system>|<value>
    """
    params = dict(request.query_params)
    adapter = get_adapter("satusehat")
    result = await adapter.inbound_search(resource_type, params)
    return {"ok": result.ok, "http_status": result.http_status,
            "data": result.bundle or result.resource, "error": result.error}
