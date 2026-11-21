"""Identity mapping endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_operator
from app.audit import logger as audit
from app.core import identity
from app.db.session import get_db
from app.models import ExternalSystem, IdentifierMapping
from app.schemas import MappingCreate

router = APIRouter(prefix="/mappings", tags=["mappings"])


def _system_id(db: Session, name: str):
    s = db.execute(select(ExternalSystem).where(ExternalSystem.name == name)).scalar_one_or_none()
    if not s:
        raise HTTPException(400, f"system '{name}' not found")
    return s.id


@router.get("")
async def list_mappings(db: Session = Depends(get_db), _: str = Depends(require_operator)):
    rows = db.execute(select(IdentifierMapping)).scalars().all()
    return [
        {
            "id": str(m.id),
            "resource_type": m.resource_type,
            "source_identifier": m.source_identifier,
            "target_identifier": m.target_identifier,
            "identifier_type": m.identifier_type,
            "validation_status": m.validation_status,
        }
        for m in rows
    ]


@router.post("")
async def create_mapping(payload: MappingCreate, db: Session = Depends(get_db),
                         actor: str = Depends(require_operator)):
    src = _system_id(db, payload.source_system)
    tgt = _system_id(db, payload.target_system)
    m = identity.upsert_mapping(
        db, resource_type=payload.resource_type, source_system_id=src, target_system_id=tgt,
        source_identifier=payload.source_identifier, target_identifier=payload.target_identifier,
        identifier_type=payload.identifier_type, validation_status=payload.validation_status,
    )
    audit.log(db, actor=actor, action="create_mapping", entity_type="IdentifierMapping", entity_id=m.id)
    db.commit()
    return {"ok": True, "id": str(m.id), "validation_status": m.validation_status}


@router.post("/{mapping_id}/verify")
async def verify_mapping(mapping_id: str, db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    m = db.get(IdentifierMapping, mapping_id)
    if not m:
        raise HTTPException(404, "mapping not found")
    m.validation_status = "verified"
    m.verified_by = actor
    from datetime import datetime, timezone
    m.verified_at = datetime.now(timezone.utc)
    audit.log(db, actor=actor, action="verify_mapping", entity_type="IdentifierMapping", entity_id=m.id)
    db.commit()
    return {"ok": True, "id": str(m.id), "validation_status": m.validation_status}
