"""Mock FHIR servers for OpenMRS, OpenEMR and SATUSEHAT.

MOCK_ROLE=ehr        -> serves /openmrs and /openemr (permissive, in-memory)
MOCK_ROLE=satusehat  -> serves /fhir-r4/v1 with SATUSEHAT profile/IHS validation
MOCK_ROLE=hapi       -> serves POST /validate (HAPI-style OperationOutcome validator)

Routes use explicit prefixes (no ambiguous /{base}/... patterns) so the
SATUSEHAT endpoints never collide with the EHR endpoints.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import uvicorn
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

MOCK_ROLE = os.environ.get("MOCK_ROLE", "ehr")
MOCK_PORT = int(os.environ.get("MOCK_PORT", "8100"))

app = FastAPI(title=f"mock-{MOCK_ROLE}")

# in-memory stores: (base, resource_type) -> {id: resource}
STORE: dict[tuple[str, str], dict[str, dict]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store(base: str, rtype: str) -> dict[str, dict]:
    return STORE.setdefault((base, rtype), {})


def _capability(base: str) -> dict:
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "fhirVersion": "4.0.1",
        "format": ["json"],
        "rest": [{
            "mode": "server",
            "resource": [
                {"type": t, "interaction": [{"code": "read"}, {"code": "search-type"},
                                            {"code": "create"}, {"code": "update"}]}
                for t in ["Patient", "Encounter", "Observation", "Organization",
                          "Location", "Practitioner"]
            ],
        }],
        "implementation": {"description": f"Mock {base}"},
    }


def _match(resource: dict, params: dict) -> bool:
    for key, val in params.items():
        if key == "_lastUpdated":
            continue
        if key == "identifier":
            ids = resource.get("identifier", [])
            if not any(i.get("value") == val for i in ids):
                return False
        elif key == "subject":
            if (resource.get("subject") or {}).get("reference") != val:
                return False
        elif key == "code":
            codings = (resource.get("code") or {}).get("coding", [])
            if not any(c.get("code") == val for c in codings):
                return False
        elif key == "patient":
            if (resource.get("subject") or {}).get("reference") != f"Patient/{val}":
                return False
        elif key == "date":
            if (resource.get("effectiveDateTime") or resource.get("issued")) != val:
                return False
    return True


# =====================================================================
# Generic EHR endpoints (one router per base)
# =====================================================================
def _build_ehr_router(base: str) -> APIRouter:
    router = APIRouter(prefix=f"/{base}")

    @router.get("/metadata")
    async def metadata():
        return _capability(base)

    @router.get("/{rtype}")
    async def search(rtype: str, request: Request):
        params = dict(request.query_params)
        store = _store(base, rtype)
        matches = [r for r in store.values() if _match(r, params)]
        return {"resourceType": "Bundle", "type": "searchset", "total": len(matches),
                "entry": [{"resource": r} for r in matches]}

    @router.get("/{rtype}/{rid}")
    async def read(rtype: str, rid: str):
        r = _store(base, rtype).get(rid)
        if not r:
            return JSONResponse({"resourceType": "OperationOutcome",
                                 "issue": [{"severity": "error", "code": "not-found"}]},
                                status_code=404)
        return r

    @router.post("/{rtype}")
    async def create(rtype: str, request: Request):
        resource = await request.json()
        rid = resource.get("id") or str(uuid.uuid4())
        resource["id"] = rid
        resource.setdefault("meta", {})["lastUpdated"] = _now()
        _store(base, rtype)[rid] = resource
        return JSONResponse(resource, status_code=201)

    @router.put("/{rtype}/{rid}")
    async def update(rtype: str, rid: str, request: Request):
        if base == "openmrs" and rtype == "Observation":
            return JSONResponse({"resourceType": "OperationOutcome",
                                 "issue": [{"severity": "error", "code": "not-supported",
                                            "diagnostics": "OpenMRS Observation is append-only"}]},
                                status_code=400)
        resource = await request.json()
        resource["id"] = rid
        resource.setdefault("meta", {})["lastUpdated"] = _now()
        _store(base, rtype)[rid] = resource
        return resource

    return router


# =====================================================================
# SATUSEHAT endpoints (explicit prefix, validated)
# =====================================================================
ss = APIRouter(prefix="/fhir-r4/v1")


def _validation_errors(rtype: str, resource: dict) -> list[str]:
    errors: list[str] = []
    if rtype == "Patient":
        ids = resource.get("identifier", [])
        if not any("ihs-number" in (i.get("system") or "") for i in ids):
            errors.append("Patient.identifier wajib memuat IHS number (system fhir.kemkes.go.id/id/ihs-number)")
    elif rtype == "Condition":
        if not (resource.get("subject") or {}).get("reference"):
            errors.append("Condition.subject wajib")
        if not (resource.get("encounter") or {}).get("reference"):
            errors.append("Condition.encounter wajib (RuleNumber 10126)")
    elif rtype == "Encounter":
        subj = (resource.get("subject") or {}).get("reference", "")
        if not subj.startswith("Patient/"):
            errors.append("Encounter.subject harus Reference Patient/{patient-ihs-number}")
        if not resource.get("status"):
            errors.append("Encounter.status wajib")
        if not (resource.get("serviceProvider") or {}).get("reference"):
            errors.append("Encounter.serviceProvider wajib (RuleNumber 10124)")
        if not resource.get("statusHistory"):
            errors.append("Encounter.statusHistory wajib (RuleNumber 10122)")
        if not resource.get("diagnosis"):
            errors.append("Encounter.diagnosis wajib (RuleNumber 10457)")
    elif rtype == "Observation":
        subj = (resource.get("subject") or {}).get("reference", "")
        if not subj.startswith("Patient/"):
            errors.append("Observation.subject harus Reference Patient/{patient-ihs-number}")
        codings = (resource.get("code") or {}).get("coding", [])
        if not any(c.get("system") == "http://loinc.org" for c in codings):
            errors.append("Observation.code wajib memakai sistem terminologi LOINC")
        if not resource.get("status"):
            errors.append("Observation.status wajib")
        if not resource.get("issued"):
            errors.append("Observation.issued wajib (RuleNumber 10296)")
    return errors


@ss.get("/metadata")
async def ss_metadata():
    return _capability("satusehat")


@ss.post("")
async def ss_transaction(request: Request):
    """FHIR transaction Bundle at base URL (resolves urn:uuid references)."""
    bundle = await request.json()
    if bundle.get("resourceType") != "Bundle" or bundle.get("type") != "transaction":
        return JSONResponse({"resourceType": "OperationOutcome",
                             "issue": [{"severity": "error", "code": "invalid",
                                        "diagnostics": "Expected transaction Bundle"}]}, status_code=400)
    # First pass: validate all, collect errors
    errors = []
    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        rtype = res.get("resourceType")
        errors.extend(_validation_errors(rtype, res))
    if errors:
        return JSONResponse({"resourceType": "OperationOutcome",
                             "issue": [{"severity": "error", "code": "invalid", "diagnostics": e} for e in errors]},
                            status_code=400)
    # Second pass: assign ids, resolve urn:uuid -> id map, store
    id_map = {}
    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        full = entry.get("fullUrl", "")
        rid = res.get("id") or str(uuid.uuid4())
        res["id"] = rid
        res.setdefault("meta", {})["lastUpdated"] = _now()
        if full.startswith("urn:uuid:"):
            id_map[full] = f"{res['resourceType']}/{rid}"
    # Third pass: rewrite urn:uuid references
    def _rewrite(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "reference" and isinstance(v, str) and v in id_map:
                    obj[k] = id_map[v]
                else:
                    _rewrite(v)
        elif isinstance(obj, list):
            for it in obj:
                _rewrite(it)
    entries = []
    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        _rewrite(res)
        _store("satusehat", res["resourceType"])[res["id"]] = res
        entries.append({"response": {"status": "201 Created",
                                     "location": f"{res['resourceType']}/{res['id']}"}})
    return JSONResponse({"resourceType": "Bundle", "type": "transaction-response", "entry": entries},
                        status_code=200)


@ss.get("/{rtype}")
async def ss_search(rtype: str, request: Request):
    params = dict(request.query_params)
    store = _store("satusehat", rtype)
    matches = [r for r in store.values() if _match(r, params)]
    return {"resourceType": "Bundle", "type": "searchset", "total": len(matches),
            "entry": [{"resource": r} for r in matches]}


@ss.get("/{rtype}/{rid}")
async def ss_read(rtype: str, rid: str):
    r = _store("satusehat", rtype).get(rid)
    if not r:
        return JSONResponse({"resourceType": "OperationOutcome",
                             "issue": [{"severity": "error", "code": "not-found"}]}, status_code=404)
    return r


@ss.post("/{rtype}")
async def ss_create(rtype: str, request: Request):
    resource = await request.json()
    errors = _validation_errors(rtype, resource)
    if errors:
        return JSONResponse({
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "code": "invalid", "diagnostics": e} for e in errors],
        }, status_code=400)
    rid = resource.get("id") or str(uuid.uuid4())
    resource["id"] = rid
    resource.setdefault("meta", {})["lastUpdated"] = _now()
    _store("satusehat", rtype)[rid] = resource
    return JSONResponse(resource, status_code=201)


# =====================================================================
# HAPI-style validator (POST /validate)
# =====================================================================
hapi = APIRouter()


def _hapi_validate_issues(rtype: str, resource: dict) -> list[dict]:
    """Return HAPI-style issue dicts (severity/code/diagnostics)."""
    msgs: list[str] = []
    if rtype == "Encounter":
        subj = (resource.get("subject") or {}).get("reference", "")
        if not subj.startswith("Patient/"):
            msgs.append("Encounter.subject harus Reference Patient/{id}")
        if not (resource.get("serviceProvider") or {}).get("reference"):
            msgs.append("Encounter.serviceProvider wajib")
        if not resource.get("statusHistory"):
            msgs.append("Encounter.statusHistory wajib")
        if not resource.get("diagnosis"):
            msgs.append("Encounter.diagnosis wajib")
    elif rtype == "Observation":
        subj = (resource.get("subject") or {}).get("reference", "")
        if not subj.startswith("Patient/"):
            msgs.append("Observation.subject harus Reference Patient/{id}")
        codings = (resource.get("code") or {}).get("coding", [])
        if not any(c.get("system") == "http://loinc.org" for c in codings):
            msgs.append("Observation.code wajib LOINC")
        if not resource.get("issued"):
            msgs.append("Observation.issued wajib")
    elif rtype == "Condition":
        if not (resource.get("subject") or {}).get("reference"):
            msgs.append("Condition.subject wajib")
        if not (resource.get("encounter") or {}).get("reference"):
            msgs.append("Condition.encounter wajib")
    elif rtype == "Patient":
        if not resource.get("identifier"):
            msgs.append("Patient.identifier wajib")
    return [{"severity": "error", "code": "processing", "diagnostics": m} for m in msgs]


@hapi.post("/validate")
async def hapi_validate(request: Request):
    body = await request.json()
    resource = body.get("resource") if isinstance(body.get("resource"), dict) else body
    rtype = (resource or {}).get("resourceType")
    issues = _hapi_validate_issues(rtype, resource or {})
    # HAPI-style OperationOutcome: issues list empty => valid
    return {"resourceType": "OperationOutcome", "issue": issues}


# =====================================================================
# SSRME viewing mock (CHLink / SHLink) - demoable without real credentials
# =====================================================================
ssrme = APIRouter(prefix="/fhir-r4/v1/ssrme")


@ssrme.post("/chl")
async def ssrme_chl(request: Request):
    body = await request.json()
    token = uuid.uuid4().hex[:12]
    return {"verificationUrl": f"https://mock-ssrme.local/consent/{token}",
            "token": token, "patient_id": body.get("patient_id")}


@ssrme.post("/shl")
async def ssrme_shl(request: Request):
    body = await request.json()
    token = uuid.uuid4().hex[:12]
    emergency = body.get("type_medical_summary") == "EMERGENCY"
    return {"shlinkUrl": f"https://mock-ssrme.local/rme/{token}",
            "token": token, "emergency": emergency,
            "patient_id": body.get("patient_id")}


# =====================================================================
# Mount routers based on role
# =====================================================================
if MOCK_ROLE == "satusehat":
    app.include_router(ss)
    app.include_router(ssrme)
elif MOCK_ROLE == "hapi":
    app.include_router(hapi)
else:
    app.include_router(_build_ehr_router("openmrs"))
    app.include_router(_build_ehr_router("openemr"))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=MOCK_PORT)
