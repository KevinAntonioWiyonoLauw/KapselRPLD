# Pengujian & Hasil

## Test otomatis

| Suite | Lokasi | Jumlah | Status |
|-------|--------|--------|--------|
| Unit (transform, validation, terminology, idempotency, satusehat_builder, conflict-version, observation-key, error-normalization, openemr adapter, openmrs transform, profile-gate, inbound helpers, ssrme, security middleware, audit fixes) | `backend/tests/unit` | 67 | ✅ lulus |
| Integration (adapter → mock, error-classification, conflict-version DB, observation idempotency, openemr pipeline, openmrs pipeline, satusehat condition, profile-gate DB, inbound policy DB, migrations) | `backend/tests/integration` | 19 | ✅ lulus |
| End-to-end (API, dua arah, konflik) | `backend/tests/e2e` | 3 | ✅ lulus |

Cara jalankan: `scripts/test-all.ps1` (lihat `docs/runbook.md`).

## Matriks Test Case (proposal 4.3.2)

| ID | Skenario | Bukti / Hasil |
|----|----------|---------------|
| TC-01 | Ambil Patient dari OpenMRS | ✅ adapter.search mengembalikan Bundle (integration test) |
| TC-02 | Kirim Patient ke OpenEMR | ✅ job success, Patient mendarat di mock OpenEMR |
| TC-03 | Kirim Encounter dgn referensi Patient | ✅ subject ditulis ulang ke `Patient/1` (mapping) di OpenEMR |
| TC-04 | Kirim Observation | ✅ LOINC 8310-5 + unit UCUM `Cel` di SATUSEHAT |
| TC-05 | Endpoint tujuan timeout | ✅ `failed_temp` + `next_attempt_at` terjadwal |
| TC-06 | Pekerjaan sama diproses ulang | ✅ idempotency: job sama; search-before-create mencegah duplikat |
| TC-07 | Data pasien tak bisa dipetakan | ✅ `needs_review` ("Identity mapping belum terverifikasi") |
| TC-08 | Data tak memenuhi profil tujuan | ✅ `needs_review` ("Observation.code wajib LOINC") |
| TC-09 | Token SATUSEHAT tidak valid | ✅ adapter memetakan 401/403 → error `auth` non-retryable (lihat catatan) |
| TC-10 | Dashboard memuat riwayat | ✅ dashboard HTTP 200, tabel job/konflik/mapping dari API |
| TC-11 | **Kirim ke SATUSEHAT sandbox NYATA (otomatis)** | ✅ Worker: Encounter→Bundle(Encounter+Condition) sukses; Observation→sukses; terverifikasi GET di sandbox |
| TC-12 | **Sinkronisasi dua arah OpenMRS↔OpenEMR** | ✅ OpenMRS→OpenEMR & OpenEMR→OpenMRS sukses; mapping dua arah tersimpan |
| TC-13 | **Deteksi konflik** | ✅ Nilai sumber≠tujuan → job `needs_review` + tercatat di `/conflicts` |
| TC-14 | **Kirim Patient+Encounter+Observation ke OpenMRS NYATA** | ✅ Patient/Encounter/Observation `success`, terverifikasi di DB OpenMRS (lihat `docs/openmrs-real-integration.md`) |

## Cakupan per suite
| Suite | Jumlah | Cakupan |
|-------|--------|---------|
| Unit | 67 | transform (termasuk aturan OpenEMR + OpenMRS: identifier preferred/type/lokasi, Encounter.type UUID), validation, terminologi, idempotency (termasuk Observation subject+code+effective), satusehat_builder (termasuk multi-diagnosis→Condition), conflict-version (F4), normalisasi error (OperationOutcome), normalisasi adapter OpenEMR, identifier-priority (F3), ekstraksi diagnosis, profile-gate helper, inbound helpers, SSRME URL, security headers/HTTPS middleware |
| Integration | 19 | adapter→mock + error-classification F2 + conflict-version F4 (DB) + observation idempotency (DB) + openemr pipeline (Encounter→Observation) + openmrs pipeline (identifier preferred + Encounter.type UUID + subject→uuid) + satusehat condition pipeline (semua diagnosis → Condition) + profile-gate (invalid→needs_review, valid→delivered) + inbound policy (tarik + idempotent) + Alembic (drift check, version table) |
| E2E | 3 | health, Patient OpenMRS→OpenEMR, conflict detection |

> Total **89 test lulus** (67 + 19 + 3). Lihat `docs/AUDIT.md` untuk status perbaikan temuan audit (F1–F4).

## Bukti SATUSEHAT Sandbox Nyata
Selain mock, integrasi **sungguhan ke sandbox SATUSEHAT** telah dijalankan dan lulus:

**1) Probe rantai penuh (manual/reproducible):**
```
docker compose exec backend python probe_satusehat.py
→ [OK] token; [OK] Organization; [OK] Patient; [OK] Practitioner; [OK] Location;
  201 Encounter; 201 Condition; [OK] Observation
```

**2) Jalur OTOMATIS via worker (mode sandbox):**
```
enqueue Encounter(ENC-SRC-1) → openmrs→satusehat  ⇒ success (transaction Bundle Encounter+Condition)
enqueue Observation(encounter=ENC-SRC-1) → satusehat ⇒ success (referensi Encounter hasil mapping)
GET /Encounter/{id} & /Observation?subject=... di sandbox ⇒ data benar-benar ada
```
Detail flow, aturan wajib (rule number), dan payload: `docs/satusehat-integration.md`.

## Bukti OpenMRS NYATA (reference application)
Integrasi **sungguhan ke OpenMRS** (image `openmrs/openmrs-reference-application-distro`, FHIR2 R4) telah dijalankan dan lulus end-to-end lewat middleware:

```
enqueue Patient     (openemr→openmrs) ⇒ success
enqueue Encounter   (openemr→openmrs) ⇒ success
enqueue Observation (openemr→openmrs) ⇒ success
verifikasi DB OpenMRS: patient_id 22, encounter 1, obs 1 (value 78)
```

Aturan FHIR2 yang dipenuhi transform (temuan nyata, bukan asumsi):
- `Patient.identifier`: `use=official` (preferred) + `type.text` = nama tipe identifier
  + `system` terdaftar di `fhir_patient_identifier_system` + extension
  `.../ext/patient/identifier#location` → `Location/{uuid}`.
- `Encounter.type`: coding sistem `http://fhir.openmrs.org/code-system/encounter-type`
  dengan `code` = UUID encounter-type.
- `Observation`: `code` LOINC dipetakan ke concept lewat `fhir_concept_source`.
Detail prasyarat, penyiapan, dan bukti: `docs/openmrs-real-integration.md`.

## Metrik (dari run demo mock)

- **Success Rate** = 100% (5/5 job sukses pada run bersih)
- **Avg Latency** ≈ 4.7 s (poll/worker interval)
- **Duplicate skips** ≥ 1 (idempotency terbukti)
- **Failure recovery** = attempt#1 `temp_error` → attempt#2 `success` (201) setelah endpoint pulih

## Catatan TC-09
Error `auth` di adapter ditandai `retryable=False`, sehingga job berakhir
`failed_perm` tanpa retry berulang — sesuai harapan "tidak mengulang tanpa batas".

## Batasan pengujian
- Data klinis uji memakai **sintetis** untuk pasien/observasi; identitas pasien memakai
  entitas sandbox nyata (IHS) agar lolos validasi SATUSEHAT.
- SATUSEHAT **sandbox** (staging) sudah diuji nyata; hasil diklasifikasikan sebagai **data uji**
  (bukan transaksi produksi).
- Latency bergantung interval polling/worker; bukan real-time (sesuai batasan proposal).
