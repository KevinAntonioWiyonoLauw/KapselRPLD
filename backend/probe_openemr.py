"""End-to-end OpenEMR probe (reproducible proof against a REAL OpenEMR).

Runs Patient -> Encounter -> Observation through the actual adapter + transforms,
then reads the created Patient back. Requires a real OpenEMR reachable at
``OPENEMR_FHIR_BASE_URL`` with the REST/FHIR API enabled.

Run inside a container on the compose network (examples):
    docker run --rm --network kapselrpld_default \
      -e OPENEMR_MODE=real \
      -e OPENEMR_FHIR_BASE_URL=http://openemr/apis/default/fhir \
      -e OPENEMR_TOKEN_URL=http://openemr/oauth2/default/token \
      -e OPENEMR_CLIENT_ID=... -e OPENEMR_CLIENT_SECRET=... \
      -e OPENEMR_USERNAME=admin -e OPENEMR_PASSWORD=pass \
      -v "$PWD/backend:/app" -w /app kapselrpld-backend:latest python probe_openemr.py

Notes:
- Password grant requires the ``oauth_password_grant`` global enabled in OpenEMR.
- Patient names must use ``use=official`` and Observations need ``category`` (the
  transforms add these for the ``openemr`` target automatically).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from app.adapters.registry import get_adapter
from app.config import settings
from app.core import transform


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


async def main() -> int:
    print(f"OpenEMR mode={settings.openemr_mode} base={settings.openemr_fhir_base_url}")
    a = get_adapter("openemr")

    cap = await a.get_capability()
    if not cap.ok:
        print("[ERR] metadata:", cap.error)
        return 1
    print(f"[OK] metadata -> {cap.http_status} {(cap.resource or {}).get('resourceType')}")

    mrn = f"PROBE-{uuid.uuid4().hex[:8]}"
    patient = transform.transform(
        {"resourceType": "Patient",
         "identifier": [{"system": "http://openemr.org/pid", "value": mrn}],
         "name": [{"family": "Probe", "given": ["OpenEMR"]}],
         "gender": "male", "birthDate": "1990-01-01"},
        "openemr", {})
    r = await a.create("Patient", patient)
    if not r.ok:
        print("[ERR] create Patient:", r.http_status, r.error)
        return 1
    pid = r.resource["id"]
    print(f"[OK] Patient created id={pid}")

    enc = transform.transform(
        {"resourceType": "Encounter", "status": "finished",
         "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
         "period": {"start": _now(), "end": _now()}},
        "openemr", {"patient_ref": f"Patient/{pid}"})
    re = await a.create("Encounter", enc)
    if not re.ok:
        print("[ERR] create Encounter:", re.http_status, re.error)
        return 1
    eid = re.resource["id"]
    print(f"[OK] Encounter created id={eid}")

    obs = transform.transform(
        {"resourceType": "Observation", "status": "final",
         "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}]},
         "valueQuantity": {"value": 80, "unit": "/min"},
         "effectiveDateTime": _now()},
        "openemr", {"patient_ref": f"Patient/{pid}", "encounter_ref": f"Encounter/{eid}"})
    ro = await a.create("Observation", obs)
    if not ro.ok:
        print("[ERR] create Observation:", ro.http_status, ro.error)
        return 1
    print(f"[OK] Observation created id={ro.resource['id']}")

    got = await a.read("Patient", pid)
    name = ""
    if got.ok and got.resource:
        names = got.resource.get("name") or [{}]
        name = names[0].get("family") or ""
    print(f"[OK] GET Patient/{pid} -> {got.http_status} name={name}")
    print("PROBE_OPENEMR_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
