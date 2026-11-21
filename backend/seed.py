"""Seed the middleware: systems, policies, identifier mappings, terminology,
and load synthetic fixtures into the mock EHR / SATUSEHAT stores.

Run inside the backend container: python seed.py
"""
from __future__ import annotations

import json
import os

import httpx
from sqlalchemy import select

from app.config import settings
from app.db.session import SessionLocal, init_db
from app.models import ExternalSystem, IdentifierMapping, SyncPolicy, TerminologyMap

FIXTURES = os.environ.get("FIXTURES_DIR", os.path.join(os.path.dirname(__file__), "fixtures"))


def _load(name: str):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


def _get_or_create_system(db, name, **kw) -> ExternalSystem:
    s = db.execute(select(ExternalSystem).where(ExternalSystem.name == name)).scalar_one_or_none()
    if s is None:
        s = ExternalSystem(name=name, **kw)
        db.add(s)
        db.flush()
    else:
        # Refresh mutable fields so re-seeding reflects the current mode/config
        # (e.g. mock <-> real base URLs), keeping the dashboard display accurate.
        for k, v in kw.items():
            setattr(s, k, v)
    return s


def seed_systems(db):
    openmrs = _get_or_create_system(
        db, "openmrs", system_type="ehr",
        fhir_base_url=settings.openmrs_mock_url if settings.openmrs_mode == "mock" else settings.openmrs_fhir_base_url,
        auth_type=settings.openmrs_auth_type, auth_config_ref="OPENMRS_*")
    openemr = _get_or_create_system(
        db, "openemr", system_type="ehr",
        fhir_base_url=settings.openemr_mock_url if settings.openemr_mode == "mock" else settings.openemr_fhir_base_url,
        auth_type="oauth2_client_credentials", auth_config_ref="OPENEMR_*")
    satusehat = _get_or_create_system(
        db, "satusehat", system_type="national_platform",
        fhir_base_url=settings.satusehat_mock_url if settings.satusehat_mode == "mock" else settings.satusehat_fhir_base_url,
        auth_type="oauth2_client_credentials", auth_config_ref="SATUSEHAT_*")
    return openmrs, openemr, satusehat


def seed_policies(db, openmrs, openemr, satusehat):
    routes = [
        (openmrs, openemr, "Patient"),
        (openmrs, openemr, "Encounter"),
        (openmrs, openemr, "Observation"),
        # Two-way OpenMRS <-> OpenEMR (Patient & Encounter bidirectional; Observation append-only in OpenMRS -> one-way only)
        (openemr, openmrs, "Patient"),
        (openemr, openmrs, "Encounter"),
        (openmrs, satusehat, "Patient"),
        (openmrs, satusehat, "Encounter"),
        (openmrs, satusehat, "Observation"),
    ]
    for src, tgt, rtype in routes:
        exists = db.execute(select(SyncPolicy).where(
            SyncPolicy.source_system_id == src.id,
            SyncPolicy.target_system_id == tgt.id,
            SyncPolicy.resource_type == rtype)).scalar_one_or_none()
        if not exists:
            two_way = rtype in ("Patient", "Encounter") and {src.name, tgt.name} == {"openmrs", "openemr"}
            db.add(SyncPolicy(
                source_system_id=src.id, target_system_id=tgt.id, resource_type=rtype,
                direction="bidirectional" if two_way else "one_way", enabled=True,
                retry_policy_json={"max_attempts": settings.retry_max_attempts},
                conflict_strategy="manual_review"))


def seed_mappings(db, openmrs, openemr, satusehat):
    rows = [
        # source MRN -> OpenEMR patient id
        (openmrs, openemr, "MRN-001", "1", "local"),
        (openmrs, openemr, "MRN-002", "2", "local"),
        # source MRN -> SATUSEHAT IHS number
        (openmrs, satusehat, "MRN-001", "100000030009", "ihs"),
        (openmrs, satusehat, "MRN-002", "100000030010", "ihs"),
        # source OpenEMR patient identifier -> SATUSEHAT IHS number
        # (melengkapi arah OpenEMR -> SATUSEHAT; Patient OpenEMR membawa identifier MRN yang sama)
        (openemr, satusehat, "MRN-001", "100000030009", "ihs"),
        (openemr, satusehat, "MRN-002", "100000030010", "ihs"),
    ]
    for src, tgt, sid, tid, itype in rows:
        exists = db.execute(select(IdentifierMapping).where(
            IdentifierMapping.source_system_id == src.id,
            IdentifierMapping.target_system_id == tgt.id,
            IdentifierMapping.source_identifier == sid)).scalar_one_or_none()
        if not exists:
            db.add(IdentifierMapping(
                resource_type="Patient", source_system_id=src.id, target_system_id=tgt.id,
                source_identifier=sid, target_identifier=tid, identifier_type=itype,
                validation_status="verified", verified_by="seed"))


def seed_terminology(db):
    concepts = {
        "body_temp": ("8310-5", "Body temperature", "Cel"),
        "heart_rate": ("8867-4", "Heart rate", "/min"),
        "body_weight": ("29463-7", "Body weight", "kg"),
        "systolic_bp": ("8480-6", "Systolic blood pressure", "mm[Hg]"),
        "diastolic_bp": ("8462-4", "Diastolic blood pressure", "mm[Hg]"),
    }
    for key, (code, display, unit) in concepts.items():
        exists = db.execute(select(TerminologyMap).where(TerminologyMap.concept_key == key)).scalar_one_or_none()
        if not exists:
            db.add(TerminologyMap(concept_key=key, source_code=key, target_system_uri="http://loinc.org",
                                  target_code=code, target_display=display, unit_code=unit))


def load_fixtures_into_mocks():
    """Push synthetic resources into the mock EHR (openmrs) and mock SATUSEHAT."""
    base_ehr = settings.openmrs_mock_url  # http://mock-ehr:8100/openmrs
    try:
        with httpx.Client(timeout=10) as client:
            for fname, rtype in [("patients.json", "Patient"),
                                 ("encounters.json", "Encounter"),
                                 ("observations.json", "Observation")]:
                for res in _load(fname)[rtype]:
                    client.post(f"{base_ehr}/{rtype}", json=res)
            # SATUSEHAT prerequisites
            prereq = _load("satusehat_prerequisites.json")
            base_ss = settings.satusehat_mock_url  # .../fhir-r4/v1
            for rtype in ("Organization", "Location", "Practitioner", "Patient"):
                if rtype in prereq:
                    client.post(f"{base_ss}/{rtype}", json=prereq[rtype])
        print("fixtures loaded into mocks")
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: could not load fixtures into mocks: {exc}")


def main():
    init_db()
    db = SessionLocal()
    try:
        openmrs, openemr, satusehat = seed_systems(db)
        seed_policies(db, openmrs, openemr, satusehat)
        seed_mappings(db, openmrs, openemr, satusehat)
        seed_terminology(db)
        db.commit()
        print("seeded: systems, policies, mappings, terminology")
    finally:
        db.close()
    load_fixtures_into_mocks()


if __name__ == "__main__":
    main()
