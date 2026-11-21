"""External system management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.registry import get_adapter
from app.api.deps import require_operator
from app.audit import logger as audit
from app.db.session import get_db
from app.models import ExternalSystem

router = APIRouter(prefix="/systems", tags=["systems"])


@router.get("")
async def list_systems(db: Session = Depends(get_db), _: str = Depends(require_operator)):
    systems = db.execute(select(ExternalSystem)).scalars().all()
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "system_type": s.system_type,
            "fhir_base_url": s.fhir_base_url,
            "auth_type": s.auth_type,
            "enabled": s.enabled,
        }
        for s in systems
    ]


@router.post("/{name}/check")
async def check_connectivity(name: str, db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    system = db.execute(select(ExternalSystem).where(ExternalSystem.name == name)).scalar_one_or_none()
    if not system:
        return {"ok": False, "error": "system not found"}
    adapter = get_adapter(name)
    result = await adapter.check_connectivity()
    audit.log(db, actor=actor, action="check_connectivity", entity_type="ExternalSystem",
              entity_id=system.id, detail={"ok": result.ok})
    db.commit()
    return {"ok": result.ok, "http_status": result.http_status, "error": result.error}


@router.get("/{name}/capability")
async def get_capability(name: str, db: Session = Depends(get_db), _: str = Depends(require_operator)):
    adapter = get_adapter(name)
    result = await adapter.check_connectivity()
    return {"ok": result.ok, "capability": result.resource, "error": result.error}
