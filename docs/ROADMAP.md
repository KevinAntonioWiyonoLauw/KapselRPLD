# ROADMAP — Middleware Interoperabilitas HL7 FHIR

Dokumen ini adalah peta jalan eksekusi. Diperbarui seiring progres.
Blueprint teknis: lihat `docs/RENCANA-PENGEMBANGAN.md` dan `docs/architecture.md`.

Legenda: `[x]` selesai · `[~]` sebagian · `[ ]` belum · `[!]` risiko/butuh keputusan

---

## 0. Ringkasan Status

| Area | Status |
|------|--------|
| Struktur repo + Docker Compose | ✅ Selesai |
| Backend FastAPI + 8 tabel DB | ✅ Selesai |
| 3 adapter (OpenMRS/OpenEMR/SATUSEHAT, mock-aware) | ✅ Selesai |
| Core pipeline (normalize/transform/identity/validate/conflict) | ✅ Selesai |
| Validasi **target-aware** (IHS/LOINC/Encounter.type) | ✅ Selesai (TC-08 terbukti) |
| Queue + worker + scheduler (poll/reconcile) | ✅ Selesai |
| Management API + metrics | ✅ Selesai |
| Mock EHR + Mock SATUSEHAT (validasi IHS/LOINC) | ✅ Selesai |
| Seed + fixtures (synthetic) | ✅ Selesai |
| E2E: Patient/Encounter/Observation → OpenEMR & SATUSEHAT | ✅ Terbukti (5/5 success) |
| Idempotency (TC-06) | ✅ Terbukti |
| Identity unmapped → needs_review (TC-07) | ✅ Terbukti |
| Validasi profil target-aware (TC-08) | ✅ Terbukti |
| Timeout → retry → recovery (TC-05) | ✅ Terbukti |
| Token invalid (TC-09) | ✅ Logika terverifikasi (auth non-retryable) |
| **SATUSEHAT sandbox NYATA (rantai penuh)** | ✅ Terbukti via `probe_satusehat.py` (Encounter+Condition+Observation 201 Created) |
| Dashboard Next.js (shadcn + grafik) | ✅ Build + serve HTTP 200 |
| Dua arah OpenMRS↔OpenEMR + conflict detection | ✅ Terbukti (mapping dua arah + conflict tercatat) |
| Test otomatis (unit 46 + integration 11 + e2e 3) | ✅ 60 hijau |
| Hardening (normalisasi error, retensi payload, rate limit aktif) | ✅ Selesai |
| CI (GitHub Actions) + skrip test-all | ✅ Selesai |
| Profil EHR asli (compose profile) | ✅ Siap (opsional, berat) |
| Fitur lanjutan (audit API+export, diagnosis mapping, auto-provision Encounter, metrics timeline, backup) | ✅ Selesai |
| Dokumentasi (arsitektur/API/config/runbook/testing/audit/rencana) | ✅ Selesai |
| Deployment demo (7 service up + demo.ps1) | ✅ Terbukti |

**Kesimpulan fase 1: MVP 3-resource end-to-end (mock) SELESAI dan terverifikasi.**

---

## 1. FASE SEGERA — Selesai ✅
- [x] Wire validasi target-aware ke `services/sync.py`
- [x] TC-08 (Observation tanpa LOINC → needs_review)
- [x] TC-05 (endpoint timeout → failed_temp + retry) + failure recovery
- [x] TC-09 (token invalid → error auth non-retryable)
- [x] Idempotency + search-before-create (tanpa duplikat)
- [x] Reconciler mengembalikan job "processing" macet

## 2. FASE DASHBOARD — Selesai ✅
- [x] Build image dashboard & `docker compose up`
- [x] 6 tab: Ringkasan, Konektivitas, Pekerjaan, Konflik, Pemetaan, Integrasi (antislop, responsif)
- [x] Tombol Cek konektivitas & Retry memanggil Management API
- [x] Error tersanitasi & badge status konsisten

## 3. FASE KUALITAS — Test Otomatis — Selesai ✅
- [x] Unit: transform, terminologi, idempotency, validation target-aware, satusehat_builder, audit fixes (20)
- [x] Integration: adapter→mock + error-classification (7)
- [x] E2E: health, Patient OpenMRS→OpenEMR, conflict detection (3)
- [x] CI: `.github/workflows/ci.yml` + `scripts/test-all.ps1`

## 4. FASE DOKUMENTASI — Selesai ✅
- [x] architecture.md, api.md, configuration.md, runbook.md, testing.md, satusehat-integration.md, README
- [x] LAPORAN-AKHIR.md (mengikuti struktur proposal) & PANDUAN-DEMO.md
- [x] ROADMAP.md

## 5. FASE INTEGRASI EHR ASLI — Siap (opsional) ✅
- [x] `docker-compose.ehr.yml` (profil `ehr`): OpenMRS + OpenEMR + DB masing-masing
- [x] Panduan di `docs/runbook.md`
- [ ] Eksekusi runtime nyata (berat; dijalankan sesuai kapasitas mesin/demo)

## 6. FASE SATUSEHAT SANDBOX — SELESAI ✅ (terbukti, termasuk otomatis)
- [x] Kredensial sandbox fasyankes diverifikasi (token + Organization valid)
- [x] Rantai penuh terbukti ke sandbox NYATA via `backend/probe_satusehat.py`
- [x] `SatusehatAdapter.transaction()` + aturan validasi (rule number) terdokumentasi
- [x] **Jalur OTOMATIS worker → sandbox**: Encounter (transaction Bundle Encounter+Condition)
      & Observation (dengan referensi Encounter hasil mapping) → sukses; mapping Encounter disimpan
- [x] Resolve IHS pasien (verified mapping / MPI by NIK) + verifikasi Patient di SATUSEHAT
- [x] Unit test builder (aturan wajib) ditambahkan
- [ ] (opsional) pilihan use case/diagnosis nyata, multi-Observation, tombol SSRME

## 7. Backlog Teknis
- [ ] `_lastUpdated` polling: samakan zona waktu/format antar sistem
- [ ] Conflict detection untuk alur update (MVP saat ini create-only)
- [ ] Normalisasi error: petakan OperationOutcome → pesan ringkas
- [ ] HAPI validator container (validasi profil nyata)
- [ ] Rate limiting & retensi payload

## 8. Pemetaan Timeline Proposal
| Minggu | Fokus | Status |
|--------|-------|--------|
| 1 | Analisis & fondasi | ✅ |
| 2 | Fondasi middleware | ✅ |
| 3 | Alur utama 3 resource | ✅ (mock) |
| 4 | Keandalan & dashboard | ✅ |
| 5 | Pengujian & demo | ✅ (mock); EHR asli opsional |

## 9. Definition of Done
- [x] `docker compose up` menyalakan db, backend, worker, scheduler, dashboard, mocks
- [x] Patient/Encounter/Observation end-to-end ke OpenEMR & SATUSEHAT (mock)
- [x] Retry, idempotency, identity-mapping, conflict-flag terbukti
- [x] Management API + dashboard (6 tab) berfungsi
- [x] Laporan metrik
- [x] Dokumentasi + runbook
- [x] Test otomatis hijau (60)
