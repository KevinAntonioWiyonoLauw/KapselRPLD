# Arsitektur

## Lapisan logis

1. **Adapter layer** — konektivitas & I/O ke sistem eksternal. Tidak mengambil
   keputusan bisnis. Kontrak seragam `AdapterInterface` (`backend/app/adapters/base.py`).
   - `OpenMRSAdapter` — Basic auth, base `/ws/fhir2/R4`. Observation append-only.
   - `OpenEMRAdapter` — OAuth2 client_credentials, base `/apis/default/fhir`.
   - `SatusehatAdapter` — OAuth2 client_credentials, base `/fhir-r4/v1`.
2. **Interoperability core** — `backend/app/core/`:
   - `normalization.py` — cek struktur dasar.
   - `transform.py` — transformasi per resource & target (IHS, LOINC, Encounter.type).
   - `identity.py` — resolusi identifier lintas sistem (hanya mapping terverifikasi).
   - `validation.py` — `light_validate` + `validate_for_target` (aturan target) + HAPI opsional.
   - `conflict.py` — deteksi konflik versi (flag manual).
   - `terminology.py` — tabel mapping LOINC tetap (3–5 konsep vital).
3. **Processing & management layer**:
   - `services/sync.py` — orkestrasi `enqueue_job` + `process_job`.
   - `queue/worker.py` — worker DB-backed (`FOR UPDATE SKIP LOCKED`).
   - `scheduler/poller.py` + `reconciler.py` — polling & pemulihan job macet.
   - `api/*` — Management API. `frontend/` — dashboard.

## Alur pemrosesan (process_job)

```
identity → transform → validate(target) → search-before-create (idempotency) → create
        → sukses / retry(temp) / needs_review(validation|identity) / failed_perm
```

## Diagram

```
        ┌───────────────┐        ┌───────────────┐        ┌────────────────┐
        │   OpenMRS     │◄──────►│   OpenEMR     │◄──────►│   SATUSEHAT    │
        │ (adapter)     │        │ (adapter)     │        │ (adapter/mock) │
        └───────┬───────┘        └───────┬───────┘        └───────┬────────┘
                │                        │                        │
                └────────────┬───────────┴────────────┬───────────┘
                             ▼                          ▼
              ┌───────────────────────────────────────────────┐
              │   ADAPTER LAYER = HUB (penyambung semua arah)  │
              │   Interoperability Core:                       │
              │   transform · identity mapping · validate ·    │
              │   policy · conflict · terminology              │
              └───────────────────────┬───────────────────────┘
                                      ▼
              ┌───────────────────────────────────────────────┐
              │ Queue/Worker · Retry · Scheduler · Audit ·     │
              │ Postgres · Management API · Dashboard          │
              └───────────────────────────────────────────────┘
```

**Adapter adalah hub pusat**: setiap pasangan sistem berkomunikasi **lewat adapter**
(bukan hanya OpenMRS sebagai sumber). Arah yang didukung:

| Sumber | Tujuan | Arah |
|--------|--------|------|
| OpenMRS | OpenEMR | Bidirectional (kebijakan per-resource) |
| OpenMRS | SATUSEHAT | Outbound |
| OpenEMR | SATUSEHAT | Outbound |
| SATUSEHAT | OpenMRS / OpenEMR | Inbound selektif (policy) |
| Middleware | OpenMRS / OpenEMR | Controlled inbound (validasi, mapping, konflik) |

Implementasi: `POST /jobs/enqueue` menerima `source_system` & `target_system` bebas;
inbound lewat `services/inbound.py` + `POST /satusehat/inbound/pull`. Identitas lintas
sistem (mis. OpenEMR ↔ SATUSEHAT) memakai `identifier_mapping` terverifikasi.

## Prinsip kunci

- Sumber kebenaran data klinis tetap di EHR; middleware simpan metadata saja.
- Pemetaan identitas **tidak** berdasarkan kemiripan nama; yang belum terverifikasi → `needs_review`.
- Konflik hanya **dideteksi** & ditandai; tidak ada merge klinis otomatis.
- Idempotency: `idempotency_key` (source+target+resource+id+version) + search-before-create.
