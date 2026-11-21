# Integrasi Nyata OpenMRS (Reference Application / FHIR2 R4)

Dokumen ini mencatat integrasi **sungguhan** middleware ke OpenMRS (bukan mock),
termasuk prasyarat, aturan yang ditegakkan FHIR2, cara penyiapan, dan bukti.

## Ringkasan
- Image: `openmrs/openmrs-reference-application-distro:latest` (OpenMRS Platform 2.4.x + FHIR2 1.2.x, R4).
- Endpoint FHIR: `/openmrs/ws/fhir2/R4` (di dalam jaringan compose: `http://openmrs:8080/openmrs/ws/fhir2/R4`).
- Auth: HTTP Basic (`admin` / `Admin123` pada reference app).
- Status: **Patient, Encounter, Observation** berhasil dibuat lewat pipeline middleware dan terverifikasi di database OpenMRS.

## Menjalankan stack OpenMRS
```bash
docker compose -f docker-compose.yml -f docker-compose.ehr.yml --profile ehr up -d openmrs-db openmrs
```
Boot pertama membuat skema (Liquibase, ratusan changeset) — perlu beberapa menit.
FHIR siap ketika `GET /openmrs/ws/fhir2/R4/metadata` mengembalikan **CapabilityStatement JSON**
(bukan halaman setup wizard HTML).

`.env` (mode nyata, nilai non-rahasia):
```
OPENMRS_MODE=real
OPENMRS_FHIR_BASE_URL=http://openmrs:8080/openmrs/ws/fhir2/R4
OPENMRS_AUTH_TYPE=basic
OPENMRS_USERNAME=admin
OPENMRS_PASSWORD=********          # hanya di .env, tidak pernah di-commit
OPENMRS_DEFAULT_LOCATION_UUID=8d6c993e-c2cc-11de-8d13-0010c6dffd0f  # "Unknown Location"
```

## Penyiapan khusus reference app (`scripts/openmrs-prepare.ps1`)
Reference application punya beberapa "celah provisioning" yang membuat FHIR2 create
gagal walau payload valid. Skrip idempotent ini menambal semuanya:

1. **Trigger `BEFORE INSERT` untuk kolom `uuid`** pada semua tabel ber-kolom `uuid`.
   FHIR2 mengirim `INSERT` dengan `uuid = NULL` eksplisit untuk tabel anak
   (`person_name`, `patient_identifier`, `encounter`, `obs`, dst). Karena nilainya
   NULL eksplisit, `DEFAULT` kolom tidak terpakai → error `Column 'uuid' cannot be null`.
   Trigger mengisi `NEW.uuid = IFNULL(NEW.uuid, UUID())`.
2. **`fhir_patient_identifier_system`**: daftarkan `identifier.system`
   (`http://openmrs.org/mrn`) → `patient_identifier_type` (Old Identification Number).
   Tanpa ini FHIR2 menolak dengan `Select a preferred identifier`.
3. **`fhir_concept_source`**: daftarkan LOINC → agar `Observation.code` (LOINC)
   dapat dipetakan ke concept. Tanpa ini: `concept: Cannot be empty or null`.
4. **Default identifier type**: set global property `emr.defaultPatientIdentifierType`.

Setelah menambah mapping identifier/concept, restart OpenMRS agar cache termuat:
```bash
docker compose -f docker-compose.yml -f docker-compose.ehr.yml --profile ehr restart openmrs
```

## Aturan FHIR2 yang dipenuhi oleh transformer
Terverifikasi langsung terhadap server nyata (bukan asumsi):

| Resource | Aturan wajib | Di mana ditangani |
|----------|--------------|-------------------|
| Patient | `identifier[].use = official` (preferred identifier) | `transform_patient` (openmrs) |
| Patient | `identifier[].type.text` = nama tipe (mis. `Old Identification Number`) — FHIR2 me-resolve tipe dari `type.text` | `transform_patient` |
| Patient | `identifier[].system` harus terdaftar di `fhir_patient_identifier_system` | `openmrs-prepare.ps1` |
| Patient | `identifier[].extension` `.../ext/patient/identifier#location` → `Location/{uuid}` (tidak boleh null) | `transform_patient` |
| Encounter | `type[].coding[]` sistem `http://fhir.openmrs.org/code-system/encounter-type`, `code` = UUID encounter-type (sistem lain → `Invalid type of request`) | `transform_encounter` |
| Encounter | `encounterDatetime` harus **sebelum** waktu server (jangan kirim tanggal masa depan) | data sumber / validasi |
| Observation | `code` LOINC harus terpetakan ke concept via `fhir_concept_source` | `openmrs-prepare.ps1` |
| Observation | append-only (tidak mendukung update) | `OpenMRSAdapter.update` → error non-retryable |
| (semua non-Patient) | `subject` harus `Patient/{uuid}` hasil mapping, bukan MRN | `sync.process_job` (identity resolve) |

## Bukti end-to-end (reproducible)
Lewat Management API (worker mode `real`):
```
POST /api/v1/jobs/enqueue  {source_system:"openemr", target_system:"openmrs", resource: Patient ...}
  ⇒ status: success
POST /api/v1/jobs/enqueue  {..., resource: Encounter, subject: Patient/<MRN>}
  ⇒ status: success   (subject ditulis ulang ke Patient/<uuid> OpenMRS)
POST /api/v1/jobs/enqueue  {..., resource: Observation (LOINC 8867-4)}
  ⇒ status: success
```
Verifikasi DB OpenMRS:
```
patient: 22 | encounters for patient: 1 | obs for patient: 1
latest obs value: 78  (obs_datetime 2026-11-20 09:05:00)
```

Idempotency: meng-enqueue ulang Patient dengan versi yang sama mengembalikan job
yang sama (status `success`), tidak membuat duplikat (search-by-identifier bekerja:
`GET /Patient?identifier=<value>` → total 1).

## Catatan
- Jangan menjalankan OpenMRS + OpenEMR nyata bersamaan pada mesin RAM kecil; jalankan bergantian.
- Rahasia (password) hanya ada di `.env` yang di-gitignore; tidak pernah di-commit/di-print.
- Untuk kembali ke mode mock: `OPENMRS_MODE=mock`, recreate `backend worker`.
