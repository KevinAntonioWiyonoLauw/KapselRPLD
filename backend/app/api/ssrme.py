"""SSRME (viewing) endpoints: CHLink & SHLink (Juknis SSRME V2.0)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.adapters.registry import get_adapter
from app.api.deps import require_operator
from app.audit import logger as audit
from app.config import settings
from app.core import ssrme

router = APIRouter(prefix="/ssrme", tags=["ssrme"])


class SsrmeRequest(BaseModel):
    patient_id: str
    patient_name: str
    practitioner_id: str
    practitioner_name: str
    organization_id: str
    organization_name: str
    emergency: bool = False


@router.post("/chlink")
async def chlink(payload: SsrmeRequest, _: str = Depends(require_operator)):
    if not settings.ssrme_enabled:
        raise HTTPException(400, "SSRME nonaktif")
    adapter = get_adapter("satusehat")
    result = await ssrme.create_chlink(
        adapter, patient_id=payload.patient_id, patient_name=payload.patient_name,
        practitioner_id=payload.practitioner_id, practitioner_name=payload.practitioner_name,
        organization_id=payload.organization_id, organization_name=payload.organization_name)
    return result


@router.post("/shlink")
async def shlink(payload: SsrmeRequest, _: str = Depends(require_operator)):
    if not settings.ssrme_enabled:
        raise HTTPException(400, "SSRME nonaktif")
    adapter = get_adapter("satusehat")
    result = await ssrme.create_shlink(
        adapter, patient_id=payload.patient_id, patient_name=payload.patient_name,
        practitioner_id=payload.practitioner_id, practitioner_name=payload.practitioner_name,
        organization_id=payload.organization_id, organization_name=payload.organization_name,
        emergency=payload.emergency)
    return result
