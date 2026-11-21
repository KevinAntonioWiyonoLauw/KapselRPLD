# Management API

Base: `http://localhost:8000/api/v1`
Auth: header `Authorization: Bearer <ADMIN_API_TOKEN>`
Swagger interaktif: `http://localhost:8000/docs`

**RBAC ringan:** dua peran. `admin` (`ADMIN_API_TOKEN`, akses penuh) dan `operator`
(`OPERATOR_API_TOKEN`, untuk retry/resolve/check/verify). Bila `OPERATOR_API_TOKEN` kosong,
hanya admin yang ada. Semua endpoint di bawah butuh minimal salah satu token di atas.
Token default `change_me_admin_token` **ditolak otomatis** bila `APP_ENV != development`.

| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/health` (di root `/health`) | liveness |
| GET | `/systems` | daftar sistem + tipe + base URL |
| POST | `/systems/{name}/check` | cek konektivitas |
| GET | `/systems/{name}/capability` | CapabilityStatement |
| GET | `/jobs?status=&resource_type=&limit=` | list job |
| GET | `/jobs/{id}` | detail job + attempts |
| POST | `/jobs/{id}/retry` | retry manual (failed_temp/failed_perm/needs_review) |
| POST | `/jobs/enqueue` | (dev) enqueue resource untuk sync |
| GET | `/conflicts` | list konflik |
| POST | `/conflicts/{id}/resolve` | tandai selesai manual |
| GET | `/mappings` | list identity mapping |
| POST | `/mappings` | tambah mapping (default pending) |
| POST | `/mappings/{id}/verify` | verifikasi mapping |
| GET | `/metrics` | success rate, latency, duplicate skips, by_status |
| GET | `/metrics/timeline` | jumlah job per jam (tren) |
| GET | `/audit` | daftar audit log (filter action/entity) |
| GET | `/audit/export.csv` | ekspor audit log (CSV) |
| GET | `/satusehat/inbound/{resource_type}?identifier=<system>\|<value>` | baca resource terpilih dari SATUSEHAT (read-only, batasan #6) |
| POST | `/ssrme/chlink` | buat CHLink (consent) SSRME |
| POST | `/ssrme/shlink` | buat SHLink (akses darurat) SSRME |

## Contoh

```bash
T=change_me_admin_token

# cek konektivitas openmrs
curl -X POST -H "Authorization: Bearer $T" http://localhost:8000/api/v1/systems/openmrs/check

# enqueue Patient -> openemr
curl -X POST -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/jobs/enqueue \
  -d '{"source_system":"openmrs","target_system":"openemr",
       "resource":{"resourceType":"Patient",
                   "identifier":[{"system":"http://openmrs.org/mrn","value":"MRN-001"}],
                   "name":[{"family":"Santoso","given":["Budi"]}],"gender":"male"}}'

# metrik
curl -H "Authorization: Bearer $T" http://localhost:8000/api/v1/metrics
```

## Status job

`pending` → `processing` → `success` | `failed_temp` (retry) | `failed_perm` |
`needs_review` (identitas tak termap / validasi gagal) | `conflict`.
