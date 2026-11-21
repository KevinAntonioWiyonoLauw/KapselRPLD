"""Pydantic request/response schemas for the Management API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MappingCreate(BaseModel):
    resource_type: str = "Patient"
    source_system: str = Field(..., description="e.g. openmrs")
    target_system: str = Field(..., description="e.g. openemr")
    source_identifier: str
    target_identifier: str
    identifier_type: str = "local"
    validation_status: str = "pending"


class ConflictResolve(BaseModel):
    note: str | None = None


class EnqueueRequest(BaseModel):
    source_system: str
    target_system: str
    resource: dict
    version: str = ""


class InboundPolicyCreate(BaseModel):
    resource_type: str = "Observation"
    target_system: str = "openmrs"
    filter: dict = Field(default_factory=dict, description="SATUSEHAT search params, e.g. {'category':'vital-signs'}")
    enabled: bool = True


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"


class JobOut(BaseModel):
    id: str
    resource_type: str
    status: str
    attempt_count: int
    source_resource_id: str | None = None
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
