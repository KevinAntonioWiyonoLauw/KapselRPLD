"""Policy-driven selective inbound from SATUSEHAT (#11).

Pulls a chosen resource type from SATUSEHAT using the policy's ``filter_json``
search params, then lands each resource in the target EHR (e.g. OpenMRS) and
records an IdentifierMapping so re-runs are idempotent (no duplicates).

This is the read/pull counterpart to the outbound pipeline. It only pulls what a
policy explicitly selects (per Batasan: inbound is selective, not a bulk mirror).
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.registry import get_adapter
from app.audit import logger as audit
from app.core import identity
from app.models import ExternalSystem, SyncPolicy


def _identity_value(resource: dict) -> str | None:
    ids = resource.get("identifier") or []
    for i in ids:
        if i.get("value"):
            return i["value"]
    # Fall back to the SATUSEHAT resource id so mappings stay stable.
    return resource.get("id")


async def pull_policy(db: Session, policy: SyncPolicy) -> dict:
    """Pull resources selected by one inbound policy. Returns a small summary."""
    source = db.get(ExternalSystem, policy.source_system_id)   # SATUSEHAT
    target = db.get(ExternalSystem, policy.target_system_id)   # EHR
    if not source or not target:
        return {"policy": str(policy.id), "ok": False, "error": "system missing"}

    params = dict(policy.filter_json or {})
    ss = get_adapter(source.name)
    res = await ss.search(policy.resource_type, params)
    if not res.ok or not res.bundle:
        return {"policy": str(policy.id), "ok": False, "pulled": 0,
                "error": (res.error or {}).get("message", "search failed")}

    entries = res.bundle.get("entry", [])
    target_adapter = get_adapter(target.name)
    pulled = created = skipped = failed = 0

    for entry in entries:
        resource = entry.get("resource")
        if not resource or resource.get("resourceType") != policy.resource_type:
            continue
        pulled += 1
        ident = _identity_value(resource)
        if not ident:
            failed += 1
            continue

        # Idempotency: skip if we already pulled this resource into the target.
        existing = identity.resolve(
            db, resource_type=policy.resource_type, source_system_id=source.id,
            target_system_id=target.id, source_identifier=ident)
        if existing is not None:
            skipped += 1
            continue

        result = await target_adapter.create(policy.resource_type, resource)
        if result.ok and result.resource and result.resource.get("id"):
            new_id = result.resource["id"]
            identity.upsert_mapping(
                db, resource_type=policy.resource_type, source_system_id=source.id,
                target_system_id=target.id, source_identifier=ident,
                target_identifier=new_id, identifier_type="local",
                validation_status="verified")
            created += 1
        else:
            failed += 1

    db.flush()
    audit.log(db, actor="scheduler", action="inbound_pull", entity_type="SyncPolicy",
              entity_id=policy.id,
              detail={"resource_type": policy.resource_type, "pulled": pulled,
                      "created": created, "skipped": skipped, "failed": failed})
    return {"policy": str(policy.id), "ok": True, "resource_type": policy.resource_type,
            "pulled": pulled, "created": created, "skipped": skipped, "failed": failed}


async def pull_once(db: Session) -> list[dict]:
    """Run every enabled inbound policy once."""
    policies = db.execute(
        select(SyncPolicy).where(
            SyncPolicy.enabled.is_(True), SyncPolicy.direction == "inbound")
    ).scalars().all()
    results = []
    for p in policies:
        try:
            results.append(await pull_policy(db, p))
        except Exception as exc:  # noqa: BLE001
            results.append({"policy": str(p.id), "ok": False, "error": str(exc)})
    db.commit()
    return results
