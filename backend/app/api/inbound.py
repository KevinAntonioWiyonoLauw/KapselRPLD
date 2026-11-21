"""Selective inbound from SATUSEHAT (read-only), per Batasan #6.

Two things live here:
- A one-off read-through: GET /satusehat/inbound/{resource_type}
- Policy-driven selective pull (#11): create/list/delete inbound policies and
  trigger a pull. The scheduler also runs enabled inbound policies periodically.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.registry import get_adapter
from app.api.deps import require_operator
from app.audit import logger as audit
from app.db.session import get_db
from app.models import ExternalSystem, SyncPolicy
from app.schemas import InboundPolicyCreate
from app.services.inbound import pull_once, pull_policy

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


def _satusehat_id(db: Session):
    s = db.execute(select(ExternalSystem).where(ExternalSystem.name == "satusehat")).scalar_one_or_none()
    if not s:
        raise HTTPException(400, "system 'satusehat' belum terdaftar")
    return s


def _policy_dict(p: SyncPolicy) -> dict:
    return {"id": str(p.id), "resource_type": p.resource_type,
            "direction": p.direction, "enabled": p.enabled,
            "filter": p.filter_json or {}}


@router.get("/inbound-policies")
async def list_inbound_policies(db: Session = Depends(get_db), _: str = Depends(require_operator)):
    rows = db.execute(select(SyncPolicy).where(SyncPolicy.direction == "inbound")).scalars().all()
    return [_policy_dict(p) for p in rows]


@router.post("/inbound-policies")
async def create_inbound_policy(payload: InboundPolicyCreate, db: Session = Depends(get_db),
                                actor: str = Depends(require_operator)):
    src = _satusehat_id(db)
    tgt = db.execute(select(ExternalSystem).where(ExternalSystem.name == payload.target_system)).scalar_one_or_none()
    if not tgt:
        raise HTTPException(400, f"system '{payload.target_system}' belum terdaftar")
    existing = db.execute(select(SyncPolicy).where(
        SyncPolicy.source_system_id == src.id, SyncPolicy.target_system_id == tgt.id,
        SyncPolicy.resource_type == payload.resource_type,
        SyncPolicy.direction == "inbound")).scalar_one_or_none()
    if existing:
        existing.filter_json = payload.filter
        existing.enabled = payload.enabled
        db.commit()
        return _policy_dict(existing)
    p = SyncPolicy(source_system_id=src.id, target_system_id=tgt.id,
                   resource_type=payload.resource_type, direction="inbound",
                   enabled=payload.enabled, filter_json=payload.filter)
    db.add(p)
    db.flush()
    audit.log(db, actor=actor, action="create_inbound_policy", entity_type="SyncPolicy",
              entity_id=p.id, detail={"resource_type": payload.resource_type, "filter": payload.filter})
    db.commit()
    return _policy_dict(p)


@router.delete("/inbound-policies/{policy_id}")
async def delete_inbound_policy(policy_id: str, db: Session = Depends(get_db),
                                actor: str = Depends(require_operator)):
    p = db.get(SyncPolicy, policy_id)
    if not p or p.direction != "inbound":
        raise HTTPException(404, "inbound policy tidak ditemukan")
    db.delete(p)
    audit.log(db, actor=actor, action="delete_inbound_policy", entity_type="SyncPolicy", entity_id=policy_id)
    db.commit()
    return {"ok": True}


@router.post("/inbound/pull")
async def trigger_pull(db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    """Run all enabled inbound policies once, now."""
    results = await pull_once(db)
    return {"ok": True, "results": results}
