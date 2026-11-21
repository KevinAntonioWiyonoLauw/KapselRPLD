# Management API

Base: `http://localhost:8000/api/v1`
Auth: header `Authorization: Bearer <TOKEN>`
Swagger interaktif: `http://localhost:8000/docs` (OpenAPI JSON: `/openapi.json`)

## Autentikasi & RBAC (3 peran)

Tiga peran, dari paling rendah ke paling tinggi:

| Peran | Token env | Hak akses |
|-------|-----------|-----------|
| **viewer** | `VIEWER_API_TOKEN` | Baca: list/detail (jobs, conflicts, mappings, systems), metrics, audit, inbound read |
| **operator** | `OPERATOR_API_TOKEN` | viewer + aksi operasional: retry job, resolve konflik, cek konektivitas, verifikasi mapping, enqueue, SSRME, inbound pull |
| **admin** | `ADMIN_API_TOKEN` | operator + perubahan konfigurasi: buat/hapus inbound policy |

- Token dibandingkan constant-time. Role yang token env-nya kosong berarti tidak ada
  (mis. hanya admin aktif). Admin token selalu memberi admin.
- `ADMIN_API_TOKEN` default (`change_me_admin_token`) **ditolak otomatis** bila
  `APP_ENV != development`.
- Endpoint `/health`, `/docs`, `/openapi.json` tidak butuh token. `/api/v1/metrics/prometheus`
  tanpa auth (scrape internal).

### Login (form username+password → peran + token)
Dashboard memakai **login form** (username + password). Akun demo tiap peran diatur di
`.env` (`ADMIN_USERNAME`/`ADMIN_PASSWORD`, `OPERATOR_*`, `VIEWER_*`). Endpoint menukar
kredensial menjadi `role` + **token API peran** (dipakai frontend sebagai Bearer lewat
cookie httpOnly).
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}'
# -> {"ok": true, "role": "admin", "token": "<ADMIN_API_TOKEN>"}
```

Login **token** (kompatibel lama / untuk API) juga didukung: kirim `{"token":"<TOKEN>"}`
→ `{"ok": true, "role": "admin", "token": "<TOKEN>"}`.

```bash
curl -s -H "Authorization: Bearer $T" http://localhost:8000/api/v1/auth/me   # {"role": "..."}
curl -s http://localhost:8000/api/v1/auth/roles                              # peran terkonfigurasi
```

## Daftar endpoint

Kolom **Peran** = peran minimum yang dibutuhkan.

| Method | Path | Peran | Fungsi |
|--------|------|-------|--------|
| GET | `/health` (root `/health`) | - | liveness |
| POST | `/auth/login` | - | tukar token → peran |
| GET | `/auth/me` | viewer | peran token saat ini |
| GET | `/auth/roles` | - | peran yang terkonfigurasi |
| GET | `/systems` | viewer | daftar sistem + tipe + base URL |
| POST | `/systems/{name}/check` | operator | cek konektivitas |
| GET | `/systems/{name}/capability` | viewer | CapabilityStatement |
| GET | `/jobs?status=&resource_type=&limit=` | viewer | list job |
| GET | `/jobs/{id}` | viewer | detail job + attempts |
| POST | `/jobs/{id}/retry` | operator | retry manual (failed_temp/failed_perm/needs_review) |
| POST | `/jobs/enqueue` | operator | enqueue resource untuk sync |
| GET | `/conflicts` | viewer | list konflik |
| POST | `/conflicts/{id}/resolve` | operator | tandai selesai manual |
| GET | `/mappings` | viewer | list identity mapping |
| POST | `/mappings` | operator | tambah mapping (default pending) |
| POST | `/mappings/{id}/verify` | operator | verifikasi mapping |
| GET | `/metrics` | viewer | success rate, latency, duplicate skips, by_status |
| GET | `/metrics/timeline` | viewer | jumlah job per jam (tren) |
| GET | `/metrics/prometheus` | - | eksposisi Prometheus (scrape internal) |
| GET | `/audit?action=&entity_type=` | viewer | daftar audit log |
| GET | `/audit/export.csv` | viewer | ekspor audit log (CSV) |
| GET | `/satusehat/inbound/{resource_type}?identifier=<system>\|<value>` | viewer | baca resource terpilih dari SATUSEHAT (read-only) |
| GET | `/satusehat/inbound-policies` | viewer | list inbound policy |
| POST | `/satusehat/inbound-policies` | admin | buat/ubah inbound policy |
| DELETE | `/satusehat/inbound-policies/{id}` | admin | hapus inbound policy |
| POST | `/satusehat/inbound/pull` | operator | jalankan semua inbound policy sekali |
| POST | `/ssrme/chlink` | operator | buat CHLink (consent) SSRME |
| POST | `/ssrme/shlink` | operator | buat SHLink (akses RME / darurat) SSRME |

## Contoh curl per grup

```bash
B=http://localhost:8000/api/v1
T=change_me_admin_token          # admin; ganti dg demo_operator_token / demo_viewer_token sesuai peran
H="Authorization: Bearer $T"
```

### Auth
```bash
curl -s -X POST $B/auth/login -H 'Content-Type: application/json' -d "{\"token\":\"$T\"}"
curl -s -H "$H" $B/auth/me
```

### Systems
```bash
curl -s -H "$H" $B/systems
curl -s -X POST -H "$H" $B/systems/openmrs/check
curl -s -H "$H" $B/systems/openmrs/capability
```

### Jobs
```bash
curl -s -H "$H" "$B/jobs?status=failed_perm&limit=20"
curl -s -H "$H" $B/jobs/<JOB_ID>
curl -s -X POST -H "$H" $B/jobs/<JOB_ID>/retry
# enqueue Patient -> openemr
curl -s -X POST -H "$H" -H 'Content-Type: application/json' $B/jobs/enqueue -d '{
  "source_system":"openmrs","target_system":"openemr",
  "resource":{"resourceType":"Patient",
    "identifier":[{"system":"http://openmrs.org/mrn","value":"MRN-001"}],
    "name":[{"family":"Santoso","given":["Budi"]}],"gender":"male"}}'
```

### Conflicts & Mappings
```bash
curl -s -H "$H" $B/conflicts
curl -s -X POST -H "$H" -H 'Content-Type: application/json' $B/conflicts/<ID>/resolve -d '{"note":"selesai"}'
curl -s -H "$H" $B/mappings
curl -s -X POST -H "$H" -H 'Content-Type: application/json' $B/mappings -d '{
  "resource_type":"Patient","source_system":"openmrs","target_system":"openemr",
  "source_identifier":"MRN-001","target_identifier":"1","identifier_type":"local"}'
curl -s -X POST -H "$H" $B/mappings/<ID>/verify
```

### Metrics & Audit
```bash
curl -s -H "$H" $B/metrics
curl -s -H "$H" $B/metrics/timeline
curl -s $B/metrics/prometheus                 # tanpa auth (scrape)
curl -s -H "$H" "$B/audit?action=manual_retry&entity_type=SyncJob"
curl -s -H "$H" $B/audit/export.csv -o audit.csv
```

### Inbound selektif (SATUSEHAT)
```bash
# baca satu-off (read-only)
curl -s -H "$H" "$B/satusehat/inbound/Patient?identifier=http://sys-ids.kemkes.go.id/patient|100000030009"
# policy: tarik Observation berkategori vital-signs ke openmrs (admin)
curl -s -X POST -H "$H" -H 'Content-Type: application/json' $B/satusehat/inbound-policies -d '{
  "resource_type":"Observation","target_system":"openmrs","filter":{"category":"vital-signs"}}'
curl -s -H "$H" $B/satusehat/inbound-policies
curl -s -X POST -H "$H" $B/satusehat/inbound/pull
curl -s -X DELETE -H "$H" $B/satusehat/inbound-policies/<ID>
```

### SSRME (CHLink / SHLink)
```bash
curl -s -X POST -H "$H" -H 'Content-Type: application/json' $B/ssrme/chlink -d '{
  "patient_id":"100000030009","patient_name":"Budi Santoso",
  "practitioner_id":"10009880010","practitioner_name":"dr. Contoh",
  "organization_id":"<ORG_ID>","organization_name":"STAGING"}'
curl -s -X POST -H "$H" -H 'Content-Type: application/json' $B/ssrme/shlink -d '{
  "patient_id":"100000030009","patient_name":"Budi Santoso",
  "practitioner_id":"10009880010","practitioner_name":"dr. Contoh",
  "organization_id":"<ORG_ID>","organization_name":"STAGING","emergency":true}'
```

## Kode status & error
- `401` token tidak ada/tidak valid; `403` peran tidak mencukupi.
- `400/422` validasi (payload ditolak).
- `429` rate limit (header `Retry-After`).
- Error mengikuti bentuk `{"detail": "..."}` (FastAPI) atau OperationOutcome saat diteruskan dari sistem tujuan.

## Status job
`pending` → `processing` → `success` | `failed_temp` (retry terjadwal) | `failed_perm` |
`needs_review` (identitas tak termap / validasi gagal) | `conflict` (perlu tinjauan manual).
