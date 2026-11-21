"""SQLAlchemy models for the middleware metadata store.

Only integration metadata is stored here — never the clinical source of truth.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class ExternalSystem(Base):
    __tablename__ = "external_systems"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    system_type: Mapped[str] = mapped_column(String(30), nullable=False)  # ehr | national_platform
    fhir_base_url: Mapped[str] = mapped_column(Text, nullable=False)
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    auth_config_ref: Mapped[str | None] = mapped_column(Text)  # name of env/secret, never credentials
    capability_json: Mapped[dict | None] = mapped_column(JSONB)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SyncPolicy(Base):
    __tablename__ = "sync_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_system_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("external_systems.id"))
    target_system_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("external_systems.id"))
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), default="one_way")  # one_way | bidirectional
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    transform_profile: Mapped[str | None] = mapped_column(String(100))
    validation_profile: Mapped[str | None] = mapped_column(String(100))
    retry_policy_json: Mapped[dict | None] = mapped_column(JSONB)
    conflict_strategy: Mapped[str] = mapped_column(String(30), default="manual_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "source_system_id", "target_system_id", "resource_type", name="uq_policy_route"
        ),
    )


class IdentifierMapping(Base):
    __tablename__ = "identifier_mapping"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    resource_type: Mapped[str] = mapped_column(String(50), default="Patient")
    source_system_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("external_systems.id"))
    source_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    target_system_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("external_systems.id"))
    target_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    identifier_type: Mapped[str] = mapped_column(String(20), default="local")  # local | nik | ihs
    validation_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|verified|rejected
    synced_version: Mapped[str | None] = mapped_column(Text)  # F4: last synced source version
    synced_target_version: Mapped[str | None] = mapped_column(Text)  # F4: last known target version
    verified_by: Mapped[str | None] = mapped_column(String(100))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "source_system_id",
            "source_identifier",
            "target_system_id",
            "resource_type",
            name="uq_identifier_mapping",
        ),
    )


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sync_policies.id"))
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_system_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("external_systems.id"))
    target_system_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("external_systems.id"))
    source_resource_id: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    # pending | processing | success | failed_temp | failed_perm | needs_review | conflict
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload_ref: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    attempts: Mapped[list["JobAttempt"]] = relationship(back_populates="job")


class JobAttempt(Base):
    __tablename__ = "job_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sync_jobs.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str | None] = mapped_column(String(20))  # success|temp_error|perm_error
    error_detail: Mapped[str | None] = mapped_column(Text)

    job: Mapped["SyncJob"] = relationship(back_populates="attempts")


class Conflict(Base):
    __tablename__ = "conflicts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sync_jobs.id"))
    resource_type: Mapped[str] = mapped_column(String(50))
    source_version: Mapped[str | None] = mapped_column(Text)
    target_version: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolution: Mapped[str] = mapped_column(String(20), default="pending")  # pending|manual_resolved
    note: Mapped[str | None] = mapped_column(Text)


class TerminologyMap(Base):
    __tablename__ = "terminology_map"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    concept_key: Mapped[str] = mapped_column(String(50), index=True)
    source_system_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("external_systems.id"))
    source_code: Mapped[str] = mapped_column(Text)
    source_system_uri: Mapped[str | None] = mapped_column(Text)
    target_system_uri: Mapped[str] = mapped_column(Text, default="http://loinc.org")
    target_code: Mapped[str] = mapped_column(Text)
    target_display: Mapped[str | None] = mapped_column(Text)
    unit_code: Mapped[str | None] = mapped_column(String(30))  # UCUM


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(100))
    detail_json: Mapped[dict | None] = mapped_column(JSONB)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
