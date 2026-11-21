"""Identity mapping service.

Resolves a source identifier to a target identifier using verified mappings only.
If no verified mapping exists the caller must STOP and route to manual review
(proposal 4.2.3 / 2.5.8 — never match by name similarity).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import IdentifierMapping


def resolve(
    db: Session,
    *,
    resource_type: str,
    source_system_id,
    target_system_id,
    source_identifier: str,
) -> IdentifierMapping | None:
    stmt = select(IdentifierMapping).where(
        IdentifierMapping.resource_type == resource_type,
        IdentifierMapping.source_system_id == source_system_id,
        IdentifierMapping.target_system_id == target_system_id,
        IdentifierMapping.source_identifier == source_identifier,
    )
    mapping = db.execute(stmt).scalar_one_or_none()
    if mapping and mapping.validation_status == "verified":
        return mapping
    return None


def upsert_mapping(
    db: Session,
    *,
    resource_type: str,
    source_system_id,
    target_system_id,
    source_identifier: str,
    target_identifier: str,
    identifier_type: str = "local",
    validation_status: str = "pending",
) -> IdentifierMapping:
    stmt = select(IdentifierMapping).where(
        IdentifierMapping.resource_type == resource_type,
        IdentifierMapping.source_system_id == source_system_id,
        IdentifierMapping.target_system_id == target_system_id,
        IdentifierMapping.source_identifier == source_identifier,
    )
    mapping = db.execute(stmt).scalar_one_or_none()
    if mapping is None:
        mapping = IdentifierMapping(
            resource_type=resource_type,
            source_system_id=source_system_id,
            target_system_id=target_system_id,
            source_identifier=source_identifier,
            target_identifier=target_identifier,
            identifier_type=identifier_type,
            validation_status=validation_status,
        )
        db.add(mapping)
    else:
        mapping.target_identifier = target_identifier
        mapping.identifier_type = identifier_type
        mapping.validation_status = validation_status
    db.flush()
    return mapping
