"""End-to-end SATUSEHAT sandbox probe (reproducible proof of the real flow).

Runs the FULL interoperability chain against the configured SATUSEHAT environment
(sandbox by default) using REAL sandbox entities:
    Token -> Organization -> Patient/Practitioner -> Location -> Condition+Encounter
    (transaction Bundle) -> Observation

Run inside the backend container:
    docker compose exec backend python probe_satusehat.py

Env used: SATUSEHAT_CLIENT_ID, SATUSEHAT_CLIENT_SECRET, SATUSEHAT_TOKEN_URL,
          SATUSEHAT_FHIR_BASE_URL, SATUSEHAT_ORG_ID,
          SS_PATIENT_IHS (default 100000030009), SS_PRACTITIONER_IHS (default 10009880010)
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx

from app.config import settings

BASE = settings.satusehat_fhir_base_url.rstrip("/")
ORG = settings.satusehat_org_id
PAT = os.environ.get("SS_PATIENT_IHS", "100000030009")
PRAC = os.environ.get("SS_PRACTITIONER_IHS", "10009880010")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def get_token(client: httpx.Client) -> str:
    r = client.post(settings.satusehat_token_url,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={"client_id": settings.satusehat_client_id,
                          "client_secret": settings.satusehat_client_secret})
    r.raise_for_status()
    tok = r.json()["access_token"]
    print(f"[OK] token acquired (…{tok[-6:]})")
    return tok


def main() -> None:
    with httpx.Client(timeout=40, verify=False) as client:  # noqa: S501 (sandbox)
        token = get_token(client)
        H = {"Authorization": f"Bearer {token}", "Accept": "application/fhir+json",
             "Content-Type": "application/json"}

        # 1. Organization
        org = client.get(f"{BASE}/Organization/{ORG}", headers=H)
        print(f"[{'OK' if org.status_code==200 else 'ERR'}] Organization {ORG} -> {org.status_code} "
              f"{org.json().get('name','') if org.status_code==200 else org.text[:200]}")

        # 2. Patient & Practitioner (real sandbox entities)
        for rt, iid in (("Patient", PAT), ("Practitioner", PRAC)):
            r = client.get(f"{BASE}/{rt}/{iid}", headers=H)
            print(f"[{'OK' if r.status_code==200 else 'ERR'}] {rt}/{iid} -> {r.status_code}")

        # 3. Location (create if none exists for org)
        loc_id = None
        ls = client.get(f"{BASE}/Location?organization=Organization/{ORG}", headers=H)
        if ls.status_code == 200 and ls.json().get("total", 0) > 0:
            loc_id = ls.json()["entry"][0]["resource"]["id"]
            print(f"[OK] existing Location {loc_id}")
        else:
            loc = {
                "resourceType": "Location",
                "identifier": [{"system": f"http://sys-ids.kemkes.go.id/location/{ORG}",
                                "value": f"LOC-{uuid.uuid4().hex[:6]}"}],
                "status": "active", "name": "Ruang Poli Umum",
                "managingOrganization": {"reference": f"Organization/{ORG}"},
            }
            r = client.post(f"{BASE}/Location", headers=H, json=loc)
            if r.status_code in (200, 201):
                loc_id = r.json()["id"]
                print(f"[OK] created Location {loc_id}")
            else:
                print(f"[ERR] Location create -> {r.status_code} {r.text[:300]}")
                return

        # 4. Condition + Encounter via transaction Bundle (circular ref via urn:uuid)
        enc_uuid, cond_uuid = str(uuid.uuid4()), str(uuid.uuid4())
        start, end = "2026-01-10T02:00:00+00:00", "2026-01-10T02:30:00+00:00"
        bundle = {
            "resourceType": "Bundle", "type": "transaction",
            "entry": [
                {"fullUrl": f"urn:uuid:{enc_uuid}", "request": {"method": "POST", "url": "Encounter"},
                 "resource": {
                     "resourceType": "Encounter", "status": "finished",
                     "identifier": [{"system": f"http://sys-ids.kemkes.go.id/encounter/{ORG}",
                                     "value": f"ENC-{uuid.uuid4().hex[:8]}"}],
                     "statusHistory": [
                         {"status": "arrived", "period": {"start": start, "end": end}},
                         {"status": "in-progress", "period": {"start": start, "end": end}},
                         {"status": "finished", "period": {"start": start, "end": end}},
                     ],
                     "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                               "code": "AMB", "display": "ambulatory"},
                     "subject": {"reference": f"Patient/{PAT}"},
                     "participant": [{"type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType", "code": "ATND"}]}],
                                      "individual": {"reference": f"Practitioner/{PRAC}"}}],
                     "period": {"start": start, "end": end},
                     "location": [{"location": {"reference": f"Location/{loc_id}"}}],
                     "serviceProvider": {"reference": f"Organization/{ORG}"},
                     "diagnosis": [{"condition": {"reference": f"urn:uuid:{cond_uuid}"},
                                    "use": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/diagnosis-role", "code": "DD"}]}}],
                 }},
                {"fullUrl": f"urn:uuid:{cond_uuid}", "request": {"method": "POST", "url": "Condition"},
                 "resource": {
                     "resourceType": "Condition",
                     "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                     "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-category", "code": "encounter-diagnosis"}]}],
                     "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "J06.9", "display": "Acute URI"}]},
                     "subject": {"reference": f"Patient/{PAT}"},
                     "encounter": {"reference": f"urn:uuid:{enc_uuid}"},
                 }},
            ],
        }
        r = client.post(BASE, headers=H, json=bundle)
        if r.status_code not in (200, 201):
            print(f"[ERR] transaction Bundle -> {r.status_code} {r.text[:600]}")
            return
        enc_id = None
        for e in r.json().get("entry", []):
            loc = e.get("response", {}).get("location", "")
            print(f"    {e.get('response',{}).get('status')} {loc}")
            if "/Encounter/" in loc:
                enc_id = loc.split("/Encounter/")[1].split("/")[0]
        print(f"[OK] Encounter+Condition created; Encounter={enc_id}")

        # 5. Observation
        obs = {
            "resourceType": "Observation", "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs", "display": "Vital Signs"}]}],
            "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}]},
            "subject": {"reference": f"Patient/{PAT}"},
            "encounter": {"reference": f"Encounter/{enc_id}"},
            "performer": [{"reference": f"Practitioner/{PRAC}"}],
            "effectiveDateTime": "2026-01-10T02:10:00+00:00",
            "issued": "2026-01-10T02:10:00+00:00",
            "valueQuantity": {"value": 78, "unit": "beats/minute", "system": "http://unitsofmeasure.org", "code": "/min"},
        }
        r = client.post(f"{BASE}/Observation", headers=H, json=obs)
        if r.status_code in (200, 201):
            print(f"[OK] Observation created id={r.json().get('id')}")
        else:
            print(f"[ERR] Observation -> {r.status_code} {r.text[:600]}")


if __name__ == "__main__":
    main()
