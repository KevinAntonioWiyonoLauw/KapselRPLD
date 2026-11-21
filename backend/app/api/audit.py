"""Audit log endpoints (FR-12): list + CSV export."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_operator
from app.db.session import get_db
from app.models import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit(
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
    _: str = Depends(require_operator),
):
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "id": r.id,
            "ts": r.ts.isoformat() if r.ts else None,
            "actor": r.actor,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "detail": r.detail_json,
            "correlation_id": str(r.correlation_id) if r.correlation_id else None,
        }
        for r in rows
    ]


@router.get("/export.csv")
async def export_audit_csv(
    limit: int = Query(default=5000, le=50000),
    db: Session = Depends(get_db),
    _: str = Depends(require_operator),
):
    rows = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "ts", "actor", "action", "entity_type", "entity_id", "detail", "correlation_id"])
    for r in rows:
        writer.writerow([r.id, r.ts.isoformat() if r.ts else "", r.actor, r.action,
                         r.entity_type or "", r.entity_id or "",
                         "" if r.detail_json is None else str(r.detail_json),
                         str(r.correlation_id) if r.correlation_id else ""])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )
