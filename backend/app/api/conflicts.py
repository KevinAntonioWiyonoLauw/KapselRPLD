"""Conflict management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_operator, require_viewer
from app.audit import logger as audit
from app.db.session import get_db
from app.models import Conflict
from app.schemas import ConflictResolve

router = APIRouter(prefix="/conflicts", tags=["conflicts"])


@router.get("")
async def list_conflicts(db: Session = Depends(get_db), _: str = Depends(require_viewer)):
    rows = db.execute(select(Conflict).order_by(Conflict.detected_at.desc())).scalars().all()
    return [
        {
            "id": str(c.id),
            "resource_type": c.resource_type,
            "source_version": c.source_version,
            "target_version": c.target_version,
            "resolution": c.resolution,
            "detected_at": c.detected_at.isoformat() if c.detected_at else None,
            "note": c.note,
        }
        for c in rows
    ]


@router.post("/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: str, payload: ConflictResolve,
                           db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    c = db.get(Conflict, conflict_id)
    if not c:
        raise HTTPException(404, "conflict not found")
    c.resolution = "manual_resolved"
    c.note = payload.note or c.note
    audit.log(db, actor=actor, action="resolve_conflict", entity_type="Conflict", entity_id=c.id)
    db.commit()
    return {"ok": True, "id": str(c.id), "resolution": c.resolution}
