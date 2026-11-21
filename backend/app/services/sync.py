"""Core sync orchestration: enqueue + process jobs.

This is the hub logic. Adapters are only used for I/O; all business decisions
(identity, transform, validate, idempotency, conflict, retry) live here.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.registry import get_adapter
from app.audit import logger as audit
from app.config import settings
from app.core import identity, transform, validation
from app.core import conflict as conflict_mod
from app.core import mpi as mpi_mod
from app.core import satusehat_builder as ss_builder
from app.models import ExternalSystem, JobAttempt, SyncJob

# F2: operational errors that warrant a retry. Programming errors are NOT here.
_RETRYABLE_EXC = (TimeoutError, ConnectionError)

BACKOFF_SECONDS = [30, 120, 600, 1800, 7200]

# F3: identifier priority by issuing system (not positional).
_IDENTIFIER_PRIORITY = (
    "https://fhir.kemkes.go.id/id/ihs-number",
    "https://fhir.kemkes.go.id/id/nik",
    "http://openmrs.org/mrn",
    "http://openemr.org/pid",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def idempotency_key(source: str, target: str, resource_type: str, source_id: str, version: str = "") -> str:
    raw = f"{source}|{target}|{resource_type}|{source_id}|{version}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_system(db: Session, name: str) -> ExternalSystem | None:
    return db.execute(select(ExternalSystem).where(ExternalSystem.name == name)).scalar_one_or_none()


def _identifier_value(resource: dict) -> str | None:
    ids = resource.get("identifier")
    if not isinstance(ids, list) or not ids:
        return None
    # F3: choose by priority system, fallback to first.
    by_system = {i.get("system"): i.get("value") for i in ids if i.get("system")}
    for sys_uri in _IDENTIFIER_PRIORITY:
        if by_system.get(sys_uri):
            return by_system[sys_uri]
    for i in ids:
        if i.get("value"):
            return i["value"]
    return None


def enqueue_job(
    db: Session,
    *,
    source_name: str,
    target_name: str,
    resource: dict,
    policy_id=None,
    source_resource_id: str | None = None,
    version: str = "",
) -> SyncJob:
    source = get_system(db, source_name)
    target = get_system(db, target_name)
    if not source or not target:
        raise ValueError("Sistem sumber/tujuan belum terdaftar")
    rtype = resource["resourceType"]
    src_id = source_resource_id or resource.get("id") or _identifier_value(resource)
    if not src_id:
        # No stable id/identifier: derive from content so distinct resources
        # never collide on the idempotency key.
        src_id = "hash:" + hashlib.sha256(
            json.dumps(resource, sort_keys=True).encode()
        ).hexdigest()[:16]
    key = idempotency_key(source_name, target_name, rtype, str(src_id), version)

    existing = db.execute(select(SyncJob).where(SyncJob.idempotency_key == key)).scalar_one_or_none()
    if existing:
        return existing

    job = SyncJob(
        policy_id=policy_id,
        resource_type=rtype,
        source_system_id=source.id,
        target_system_id=target.id,
        source_resource_id=str(src_id),
        idempotency_key=key,
        status="pending",
        payload_ref=json.dumps(resource),
    )
    db.add(job)
    db.flush()
    audit.log(db, actor="system", action="enqueue_job", entity_type="SyncJob",
              entity_id=job.id, detail={"resource_type": rtype, "source": source_name,
                                        "target": target_name})
    return job


def _patient_source_id(job: SyncJob, resource: dict) -> str | None:
    if job.resource_type == "Patient":
        return _identifier_value(resource) or job.source_resource_id
    ref = (resource.get("subject") or {}).get("reference")
    if ref:
        return ref.split("/")[-1]
    return None


def _sync_mapping_for(db: Session, job: SyncJob):
    """Return the identifier mapping row for this job (any status) or None."""
    from app.models import IdentifierMapping
    if job.resource_type == "Patient":
        resource = json.loads(job.payload_ref or "{}")
        sid = _identifier_value(resource) or job.source_resource_id
        rt = "Patient"
    elif job.resource_type == "Encounter":
        sid = job.source_resource_id
        rt = "Encounter"
    else:
        return None
    return db.execute(select(IdentifierMapping).where(
        IdentifierMapping.source_system_id == job.source_system_id,
        IdentifierMapping.target_system_id == job.target_system_id,
        IdentifierMapping.resource_type == rt,
        IdentifierMapping.source_identifier == sid)).scalar_one_or_none()


def _record_sync_baselines(db: Session, job: SyncJob, resource: dict, target_version: str | None) -> None:
    """Record the source & target versions we just synchronized (F4 baselines)."""
    m = _sync_mapping_for(db, job)
    if m is not None:
        m.synced_version = (resource.get("meta") or {}).get("lastUpdated")
        m.synced_target_version = target_version


def _observation_key(resource: dict) -> dict:
    """Business key for append-only Observation: subject + code + effective time.

    Used to search the target for an existing Observation so identical writes are
    deduplicated (OpenMRS Observations are append-only, so re-sends are common).
    """
    params: dict = {}
    ref = (resource.get("subject") or {}).get("reference", "")
    if ref:
        params["subject"] = ref
    code = resource.get("code", {})
    if code.get("coding"):
        params["code"] = code["coding"][0].get("code")
    effective = resource.get("effectiveDateTime") or resource.get("issued")
    if effective:
        params["date"] = effective
    return params


def _search_params(resource: dict, target: str | None = None) -> dict:
    rtype = resource["resourceType"]
    if rtype == "Patient":
        val = _identifier_value(resource)
        return {"identifier": val} if val else {}
    if rtype == "Encounter":
        ref = (resource.get("subject") or {}).get("reference", "")
        return {"subject": ref} if ref else {}
    if rtype == "Observation":
        # OpenEMR rejects the `subject` search param on Observation; skip search
        # (create-only) for that target. Other targets use the de-dup business key.
        if target == "openemr":
            return {}
        # F7/idempotency: subject + code + effective (append-only de-dup key)
        return _observation_key(resource)
    return {}


def _schedule_retry(job: SyncJob, attempt: int) -> None:
    idx = min(attempt - 1, len(BACKOFF_SECONDS) - 1)
    job.next_attempt_at = _now() + timedelta(seconds=BACKOFF_SECONDS[idx])


def _satusehat_bundle_resources(bundle: dict) -> list[dict]:
    """Resources inside a transaction Bundle that carry a profile (skip Condition
    refs). Used to validate the deliverable payload before sending."""
    return [e.get("resource", {}) for e in bundle.get("entry", [])
            if e.get("resource", {}).get("resourceType") in ("Encounter", "Observation", "Patient")]


async def _profile_gate(db: Session, job: SyncJob, resources: list[dict], record) -> bool:
    """Validate resources against the SATUSEHAT profile before delivery.

    Returns True when valid (or validation disabled); on failure it sets the job
    to needs_review and returns False so the caller stops before sending.
    """
    if not settings.use_hapi_validator:
        return True
    all_issues: list[str] = []
    for res in resources:
        vr = await validation.profile_validate(res, "satusehat")
        if not vr.ok:
            all_issues.extend(vr.issues)
    if all_issues:
        job.status = "needs_review"
        job.last_error = "Validasi profil SATUSEHAT gagal: " + "; ".join(all_issues[:5])
        record("perm_error", err=job.last_error)
        audit.log(db, actor="worker", action="profile_validation_failed",
                  entity_type="SyncJob", entity_id=job.id, detail={"issues": all_issues[:5]})
        return False
    return True


async def _process_satusehat(db: Session, job: SyncJob, resource: dict, record) -> SyncJob:
    """Automatic pipeline: OpenMRS resource -> SATUSEHAT (real sandbox/production)."""
    org = settings.satusehat_org_id
    if not org:
        job.status = "needs_review"
        job.last_error = "SATUSEHAT_ORG_ID belum dikonfigurasi"
        record("perm_error", err=job.last_error)
        return job

    source = db.get(ExternalSystem, job.source_system_id)
    ss = get_adapter("satusehat")
    prac = settings.satusehat_practitioner_ihs
    rtype = resource.get("resourceType")

    # Resolve patient IHS: verified mapping first, else MPI by NIK, else source id if numeric.
    mapping = identity.resolve(db, resource_type="Patient", source_system_id=source.id,
                               target_system_id=job.target_system_id,
                               source_identifier=_patient_source_id(job, resource) or "")
    ihs = mapping.target_identifier if mapping else None
    if not ihs and rtype == "Patient":
        nik = _identifier_value(resource)
        if nik:
            ihs = await mpi_mod.resolve_ihs_by_nik(ss, nik)
            if ihs:
                identity.upsert_mapping(db, resource_type="Patient", source_system_id=source.id,
                                        target_system_id=job.target_system_id, source_identifier=nik,
                                        target_identifier=ihs, identifier_type="ihs",
                                        validation_status="verified")
    if not ihs:
        job.status = "needs_review"
        job.last_error = "IHS pasien tidak dapat di-resolve (MPI/mapping)"
        record("perm_error", err=job.last_error)
        audit.log(db, actor="worker", action="needs_review", entity_type="SyncJob",
                  entity_id=job.id, detail={"reason": "ihs_unresolved"})
        return job

    try:
        if rtype == "Patient":
            # Ensure the patient exists in SATUSEHAT (GET by IHS). IHS patients are pre-existing.
            got = await ss.read("Patient", ihs)
            if got.ok:
                job.status = "success"; job.last_error = None
                record("success", http_status=got.http_status, err="patient exists in SATUSEHAT")
            else:
                job.status = "needs_review"
                job.last_error = f"Patient IHS {ihs} tidak ditemukan di SATUSEHAT"
                record("perm_error", err=job.last_error)
            return job

        if rtype == "Encounter":
            loc = await ss_builder.ensure_location(ss, org)
            if not loc:
                job.status = "failed_temp"
                job.last_error = "Gagal menyiapkan Location"
                _schedule_retry(job, job.attempt_count); record("temp_error", err=job.last_error)
                return job
            diagnoses = _diagnoses_from_resource(resource)
            bundle, enc_uuid = ss_builder.build_encounter_condition_bundle(
                org=org, patient_ihs=ihs, practitioner_ihs=prac, location_id=loc,
                diagnoses=diagnoses or None)
            if not await _profile_gate(db, job, _satusehat_bundle_resources(bundle), record):
                return job
            res = await ss.transaction(bundle)
            if res.ok:
                enc_id = None
                for e in res.resource.get("entry", []):
                    loc_url = e.get("response", {}).get("location", "")
                    if "/Encounter/" in loc_url:
                        enc_id = loc_url.split("/Encounter/")[1].split("/")[0]
                if enc_id:
                    identity.upsert_mapping(db, resource_type="Encounter", source_system_id=source.id,
                                            target_system_id=job.target_system_id,
                                            source_identifier=job.source_resource_id,
                                            target_identifier=enc_id, identifier_type="local",
                                            validation_status="verified")
                job.status = "success"; job.last_error = None
                record("success", http_status=res.http_status, err=f"encounter={enc_id}")
            else:
                _finish_error(job, res, record, job.attempt_count)
            return job

        if rtype == "Observation":
            enc_map = identity.resolve(db, resource_type="Encounter", source_system_id=source.id,
                                       target_system_id=job.target_system_id,
                                       source_identifier=_encounter_source_id(resource) or "")
            if enc_map:
                encounter_target_id = enc_map.target_identifier
            else:
                # Auto-provision an Encounter (+Condition) so the Observation can be delivered
                loc = await ss_builder.ensure_location(ss, org)
                if not loc:
                    job.status = "failed_temp"; job.last_error = "Gagal menyiapkan Location"
                    _schedule_retry(job, job.attempt_count); record("temp_error", err=job.last_error)
                    return job
                bundle, _ = ss_builder.build_encounter_condition_bundle(
                    org=org, patient_ihs=ihs, practitioner_ihs=prac, location_id=loc)
                if not await _profile_gate(db, job, _satusehat_bundle_resources(bundle), record):
                    return job
                eres = await ss.transaction(bundle)
                if not eres.ok:
                    _finish_error(job, eres, record, job.attempt_count); return job
                encounter_target_id = None
                for e in eres.resource.get("entry", []):
                    loc_url = e.get("response", {}).get("location", "")
                    if "/Encounter/" in loc_url:
                        encounter_target_id = loc_url.split("/Encounter/")[1].split("/")[0]
                if not encounter_target_id:
                    job.status = "failed_temp"; job.last_error = "Encounter otomatis gagal dibuat"
                    _schedule_retry(job, job.attempt_count); record("temp_error", err=job.last_error)
                    return job
                identity.upsert_mapping(
                    db, resource_type="Encounter", source_system_id=source.id,
                    target_system_id=job.target_system_id,
                    source_identifier=_encounter_source_id(resource) or job.source_resource_id,
                    target_identifier=encounter_target_id, identifier_type="local",
                    validation_status="verified")
                audit.log(db, actor="worker", action="auto_provision_encounter", entity_type="SyncJob",
                          entity_id=job.id, detail={"encounter": encounter_target_id})
            code, display, unit = _obs_terminology(resource)
            value = (resource.get("valueQuantity") or {}).get("value", 0)
            obs = ss_builder.build_observation(
                patient_ihs=ihs, practitioner_ihs=prac, encounter_id=encounter_target_id,
                loinc_code=code, loinc_display=display, value=value, unit_code=unit)
            if not await _profile_gate(db, job, [obs], record):
                return job
            res = await ss.create("Observation", obs)
            if res.ok:
                job.status = "success"; job.last_error = None
                record("success", http_status=res.http_status)
            else:
                _finish_error(job, res, record, job.attempt_count)
            return job

        job.status = "failed_perm"
        job.last_error = f"Resource {rtype} belum didukung untuk SATUSEHAT"
        record("perm_error", err=job.last_error)
        return job
    except _RETRYABLE_EXC as exc:
        job.status = "failed_temp"; job.last_error = f"Retryable error: {exc}"
        _schedule_retry(job, job.attempt_count); record("temp_error", err=str(exc))
        audit.log(db, actor="worker", action="sync_retryable", entity_type="SyncJob",
                  entity_id=job.id, detail={"error": str(exc)})
        return job
    except Exception as exc:  # noqa: BLE001  (F2: programming error -> fail hard, no retry)
        job.status = "failed_perm"; job.last_error = f"Unhandled error: {exc}"
        record("perm_error", err=str(exc))
        audit.log(db, actor="worker", action="sync_unhandled", entity_type="SyncJob",
                  entity_id=job.id, detail={"error": str(exc), "type": type(exc).__name__})
        return job


def _finish_error(job: SyncJob, res, record, attempt_no: int) -> None:
    err = res.error or {}
    if err.get("retryable") and attempt_no < settings.retry_max_attempts:
        job.status = "failed_temp"; job.last_error = err.get("message")
        _schedule_retry(job, attempt_no); record("temp_error", http_status=res.http_status, err=err.get("detail"))
    else:
        job.status = "needs_review" if err.get("category") == "validation" else "failed_perm"
        job.last_error = err.get("message")
        record("perm_error", http_status=res.http_status, err=err.get("detail"))


def _encounter_source_id(resource: dict) -> str | None:
    ref = (resource.get("encounter") or {}).get("reference")
    return ref.split("/")[-1] if ref else None


def _encounter_target_ref(db: Session, job: SyncJob, resource: dict, source, target) -> str | None:
    """Resolve the target Encounter reference for an Observation via mapping.

    OpenEMR requires Observation.encounter; the source Encounter id must be mapped
    to the target Encounter id during the Encounter sync.
    """
    src_enc = _encounter_source_id(resource)
    if not src_enc:
        return None
    m = identity.resolve(db, resource_type="Encounter", source_system_id=source.id,
                         target_system_id=target.id, source_identifier=src_enc)
    if m is None:
        return None
    return f"Encounter/{m.target_identifier}"


def _diagnoses_from_resource(resource: dict) -> list[tuple[str, str]]:
    """Extract all ICD-10 diagnoses from the source Encounter payload.

    Supports (in priority order):
    - ``diagnoses``: list of {code, display} or [code, display]
    - custom fields ``diagnosis_code``/``icd10`` (+ ``diagnosis_display``)
    - ``reasonCode`` codings with an ICD-10 system (all of them)
    - ``Condition`` resources embedded with an ICD-10 coding
    Returns a de-duplicated ordered list of (code, display). Empty list means the
    caller should fall back to the configured default diagnosis.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(code, display):
        code = (code or "").strip()
        if code and code not in seen:
            seen.add(code)
            out.append((code, display or code))

    # 1) explicit structured list
    for d in resource.get("diagnoses", []) or []:
        if isinstance(d, dict):
            add(d.get("code") or d.get("icd10"), d.get("display"))
        elif isinstance(d, (list, tuple)) and d:
            add(d[0], d[1] if len(d) > 1 else None)

    # 2) single custom fields
    diag = resource.get("diagnosis_code") or resource.get("icd10")
    if isinstance(diag, str) and diag.strip():
        add(diag, resource.get("diagnosis_display"))

    # 3) reasonCode codings (all ICD-10 entries)
    for rc in resource.get("reasonCode", []) or []:
        for c in rc.get("coding", []) or []:
            if c.get("system", "").endswith("icd-10") and c.get("code"):
                add(c["code"], c.get("display"))

    # 4) embedded Condition resources
    for cond in resource.get("condition", []) or []:
        if isinstance(cond, dict) and cond.get("resourceType") == "Condition":
            for c in (cond.get("code") or {}).get("coding", []) or []:
                if c.get("system", "").endswith("icd-10") and c.get("code"):
                    add(c["code"], c.get("display"))

    return out


def _same_content(existing: dict, transformed: dict, resource_type: str) -> bool:
    """Compare clinically-relevant fields (ignore id/meta/identifier systems)."""
    def norm(r: dict) -> dict:
        d = {k: v for k, v in r.items() if k not in ("id", "meta", "text")}
        if resource_type == "Patient":
            return {"name": d.get("name"), "gender": d.get("gender"),
                    "birthDate": d.get("birthDate")}
        if resource_type == "Encounter":
            return {"status": d.get("status"), "period": d.get("period"),
                    "class": d.get("class")}
        if resource_type == "Observation":
            return {"status": d.get("status"), "code": d.get("code"),
                    "valueQuantity": d.get("valueQuantity"),
                    "effectiveDateTime": d.get("effectiveDateTime")}
        return d
    return norm(existing) == norm(transformed)


def _obs_terminology(resource: dict) -> tuple[str, str, str]:
    code = resource.get("code", {})
    if code.get("coding"):
        c = code["coding"][0]
        return c.get("code", "8867-4"), c.get("display", "Heart rate"), \
            (resource.get("valueQuantity") or {}).get("unit", "/min")
    from app.core import terminology
    key = code.get("text")
    mapped = terminology.resolve_by_source_code(key) if key else None
    if mapped:
        return mapped["code"], mapped["display"], mapped["unit"]
    return "8867-4", "Heart rate", "/min"


async def process_job(db: Session, job: SyncJob) -> SyncJob:
    """Execute a single sync job and record observability metrics (#16)."""
    import time
    from app.core import metrics as prom
    t0 = time.perf_counter()
    result = await _process_job_impl(db, job)
    try:
        target = db.get(ExternalSystem, job.target_system_id)
        prom.record_job(job.resource_type, target.name if target else "unknown",
                        result.status, time.perf_counter() - t0)
    except Exception:  # noqa: BLE001  (metrics must never break processing)
        pass
    return result


async def _process_job_impl(db: Session, job: SyncJob) -> SyncJob:
    """Execute a single sync job. Mutates job.status and records an attempt."""
    source = db.get(ExternalSystem, job.source_system_id)
    target = db.get(ExternalSystem, job.target_system_id)
    resource = json.loads(job.payload_ref or "{}")
    attempt_no = job.attempt_count + 1
    job.attempt_count = attempt_no
    started = _now()

    def record(outcome: str, http_status=None, err=None):
        db.add(JobAttempt(job_id=job.id, attempt_no=attempt_no, started_at=started,
                          finished_at=_now(), http_status=http_status, outcome=outcome,
                          error_detail=(err or "")[:1000]))

    try:
        # Route to the SATUSEHAT automatic pipeline when running against real env.
        if target.name == "satusehat" and settings.satusehat_mode in ("sandbox", "production"):
            return await _process_satusehat(db, job, resource, record)

        ctx: dict = {}
        src_pid = _patient_source_id(job, resource)
        # 1. Identity resolution for cross-system targets
        #    - satusehat: any resource needs the IHS number (Patient attaches it,
        #      others reference Patient/{ihs}).
        #    - openemr/openmrs: non-Patient resources need the subject mapped to a
        #      local target id (OpenMRS requires Patient/<uuid> references).
        needs_identity = (
            (target.name == "satusehat")
            or (target.name in ("openemr", "openmrs") and job.resource_type != "Patient")
        )
        if needs_identity and src_pid:
            mapping = identity.resolve(
                db, resource_type="Patient",
                source_system_id=source.id, target_system_id=target.id,
                source_identifier=src_pid,
            )
            if mapping is None:
                job.status = "needs_review"
                job.last_error = f"Identity mapping belum terverifikasi untuk {src_pid}"
                record("perm_error", err=job.last_error)
                audit.log(db, actor="worker", action="needs_review", entity_type="SyncJob",
                          entity_id=job.id, detail={"reason": "identity_unmapped"})
                return job
            if target.name == "satusehat":
                ctx["ihs_number"] = mapping.target_identifier
                ctx["patient_ref"] = f"Patient/{mapping.target_identifier}"
            else:
                ctx["patient_ref"] = f"Patient/{mapping.target_identifier}"

        # OpenEMR stores Observations as encounter forms -> need the target Encounter ref.
        if target.name == "openemr" and job.resource_type == "Observation":
            enc_ref = _encounter_target_ref(db, job, resource, source, target)
            if enc_ref:
                ctx["encounter_ref"] = enc_ref

        # 2. Transform for target profile
        transformed = transform.transform(resource, target.name, ctx)

        # 3. Validate (light + target-aware + optional HAPI profile)
        vr = validation.validate_for_target(transformed, target.name)
        if not vr.ok:
            job.status = "needs_review"
            job.last_error = "Validasi gagal: " + "; ".join(vr.issues)
            record("perm_error", err=job.last_error)
            audit.log(db, actor="worker", action="validation_failed", entity_type="SyncJob",
                      entity_id=job.id, detail={"issues": vr.issues})
            return job
        if settings.use_hapi_validator:
            pv = await validation.profile_validate(transformed, target.name)
            if not pv.ok:
                job.status = "needs_review"
                job.last_error = "Validasi profil (HAPI) gagal: " + "; ".join(pv.issues[:5])
                record("perm_error", err=job.last_error)
                audit.log(db, actor="worker", action="profile_validation_failed",
                          entity_type="SyncJob", entity_id=job.id, detail={"issues": pv.issues[:5]})
                return job

        # 4. Look up existing resource in target (idempotency + conflict detection)
        target_adapter = get_adapter(target.name)
        params = _search_params(transformed, target.name)
        if params:
            sr = await target_adapter.search(job.resource_type, params)
            if sr.ok and sr.bundle and sr.bundle.get("total", 0) > 0:
                existing_res = sr.bundle["entry"][0]["resource"]
                if _same_content(existing_res, transformed, job.resource_type):
                    job.status = "success"
                    job.last_error = None
                    record("success", http_status=sr.http_status, err="idempotent: already exists")
                    audit.log(db, actor="worker", action="sync_idempotent_skip", entity_type="SyncJob",
                              entity_id=job.id, detail={"target": target.name})
                    return job
                # F4: version-based conflict detection (content heuristic as fallback).
                src_ver = (resource.get("meta") or {}).get("lastUpdated")
                tgt_ver = (existing_res.get("meta") or {}).get("lastUpdated")
                m = _sync_mapping_for(db, job)
                base_src = getattr(m, "synced_version", None) if m else None
                base_tgt = getattr(m, "synced_target_version", None) if m else None

                action = None
                if src_ver and tgt_ver and base_src and base_tgt:
                    action = conflict_mod.classify_version_conflict(
                        source_version=src_ver, target_version=tgt_ver,
                        baseline_source=base_src, baseline_target=base_tgt)
                else:
                    # Fallback when version history is incomplete: rely on content.
                    action = "idempotent" if _same_content(existing_res, transformed, job.resource_type) else "conflict"

                if action == "idempotent":
                    job.status = "success"
                    job.last_error = None
                    record("success", http_status=sr.http_status, err="idempotent: already exists")
                    audit.log(db, actor="worker", action="sync_idempotent_skip", entity_type="SyncJob",
                              entity_id=job.id, detail={"target": target.name})
                    return job
                if action == "target_newer":
                    # Only the target changed since last sync -> target wins, nothing to do.
                    job.status = "success"
                    job.last_error = None
                    record("success", http_status=sr.http_status,
                           err="no-conflict: target changed, source unchanged")
                    audit.log(db, actor="worker", action="sync_no_conflict", entity_type="SyncJob",
                              entity_id=job.id, detail={"baseline_source": base_src})
                    return job
                if action == "source_newer":
                    # Only the source changed -> push a controlled update to the target.
                    existing_id = existing_res.get("id")
                    upd = await target_adapter.update(job.resource_type, existing_id, transformed) if existing_id else None
                    if upd is not None and upd.ok:
                        new_tgt_ver = ((upd.resource or {}).get("meta") or {}).get("lastUpdated") or tgt_ver
                        _record_sync_baselines(db, job, resource, new_tgt_ver)
                        job.status = "success"
                        job.last_error = None
                        record("success", http_status=upd.http_status, err="updated (source changed)")
                        audit.log(db, actor="worker", action="sync_update", entity_type="SyncJob",
                                  entity_id=job.id, detail={"target": target.name, "id": existing_id})
                        return job
                    # Update failed -> fall through to conflict so a human can review.
                # action == "conflict" (or update failed): record and route to manual review.
                from app.models import Conflict
                db.add(Conflict(
                    job_id=job.id, resource_type=job.resource_type,
                    source_version=src_ver or "n/a",
                    target_version=tgt_ver or "n/a",
                    resolution="pending",
                    note="Versi sumber dan tujuan sama-sama berubah; perlu peninjauan manual."))
                db.flush()
                job.status = "needs_review"
                job.last_error = "Konflik data: sumber dan tujuan sama-sama berubah; perlu peninjauan manual"
                record("perm_error", err=job.last_error)
                audit.log(db, actor="worker", action="conflict_detected", entity_type="SyncJob",
                          entity_id=job.id, detail={"target": target.name,
                                                    "source_version": src_ver, "target_version": tgt_ver})
                return job

        # 5. Create on target
        result = await target_adapter.create(job.resource_type, transformed)

        if result.ok:
            # Store bidirectional identity mapping for Patient (enables two-way sync)
            if job.resource_type == "Patient" and result.resource and result.resource.get("id"):
                new_id = result.resource["id"]
                src_pid = _patient_source_id(job, resource)
                if src_pid:
                    identity.upsert_mapping(db, resource_type="Patient", source_system_id=source.id,
                                            target_system_id=target.id, source_identifier=src_pid,
                                            target_identifier=new_id, validation_status="verified")
                    identity.upsert_mapping(db, resource_type="Patient", source_system_id=target.id,
                                            target_system_id=source.id, source_identifier=new_id,
                                            target_identifier=src_pid, validation_status="verified")
                    _record_sync_baselines(db, job, resource, (result.resource.get("meta") or {}).get("lastUpdated"))
            # Store Encounter mapping so dependent Observations can reference it.
            if job.resource_type == "Encounter" and result.resource and result.resource.get("id"):
                identity.upsert_mapping(
                    db, resource_type="Encounter", source_system_id=source.id,
                    target_system_id=target.id, source_identifier=job.source_resource_id,
                    target_identifier=result.resource["id"], identifier_type="local",
                    validation_status="verified")
                _record_sync_baselines(db, job, resource, (result.resource.get("meta") or {}).get("lastUpdated"))
            job.status = "success"
            job.last_error = None
            record("success", http_status=result.http_status)
            audit.log(db, actor="worker", action="sync_success", entity_type="SyncJob",
                      entity_id=job.id, detail={"target": target.name})
        else:
            err = result.error or {}
            if err.get("retryable") and attempt_no < settings.retry_max_attempts:
                job.status = "failed_temp"
                job.last_error = err.get("message")
                _schedule_retry(job, attempt_no)
                record("temp_error", http_status=result.http_status, err=err.get("detail"))
            else:
                job.status = "needs_review" if err.get("category") == "validation" else "failed_perm"
                job.last_error = err.get("message")
                record("perm_error", http_status=result.http_status, err=err.get("detail"))
                audit.log(db, actor="worker", action="sync_failed", entity_type="SyncJob",
                          entity_id=job.id, detail={"error": err})
        return job
    except _RETRYABLE_EXC as exc:
        job.status = "failed_temp"
        job.last_error = f"Retryable error: {exc}"
        _schedule_retry(job, attempt_no)
        record("temp_error", err=str(exc))
        audit.log(db, actor="worker", action="sync_retryable", entity_type="SyncJob",
                  entity_id=job.id, detail={"error": str(exc)})
        return job
    except Exception as exc:  # noqa: BLE001  (F2: programming error -> fail hard, no retry)
        job.status = "failed_perm"
        job.last_error = f"Unhandled error: {exc}"
        record("perm_error", err=str(exc))
        audit.log(db, actor="worker", action="sync_unhandled", entity_type="SyncJob",
                  entity_id=job.id, detail={"error": str(exc), "type": type(exc).__name__})
        return job
