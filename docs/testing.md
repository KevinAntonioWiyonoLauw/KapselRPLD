# Pengujian & Hasil

## Test otomatis

| Suite | Lokasi | Jumlah | Status |
|-------|--------|--------|--------|
| Unit (transform, validation, terminology, idempotency, satusehat_builder, conflict-version, audit fixes) | `backend/tests/unit` | 29 | ✅ lulus |
| Integration (adapter → mock, error-classification, conflict-version DB) | `backend/tests/integration` | 10 | ✅ lulus |
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

## Cakupan per suite
| Suite | Jumlah | Cakupan |
|-------|--------|---------|
| Unit | 29 | transform, validation, terminologi, idempotency, satusehat_builder, conflict-version (F4), identifier-priority (F3) |
| Integration | 10 | adapter→mock + error-classification F2 + conflict-version F4 (DB) |
| E2E | 3 | health, Patient OpenMRS→OpenEMR, conflict detection |

> Total **42 test lulus** (29 + 10 + 3). Lihat `docs/AUDIT.md` untuk status perbaikan temuan audit (F1–F4).

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
