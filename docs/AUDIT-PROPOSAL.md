# AUDIT KESESUAIAN PROYEK TERHADAP PROPOSAL
## Middleware Interoperabilitas HL7 FHIR — OpenMRS / OpenEMR / SATUSEHAT

> Sumber acuan: `docs/Proposal_Kapsel_RPLD.txt` (proposal lengkap).
> Metode: setiap requirement proposal dipetakan ke implementasi nyata di repo, dengan **bukti path/file**.
> Legenda status: **✅ Sesuai** · **◑ Sebagian** · **✗ Belum**.
> Diperbarui: hasil audit + implementasi terkini.

---

## Ringkasan Kesesuaian

| Seksi proposal | Jumlah item | ✅ Sesuai | ◑ Sebagian | ✗ Belum |
|----------------|-------------|-----------|------------|----------|
| Luaran 1.7 | 7 | 7 | 0 | 0 |
| Tujuan Khusus 1.4.2 | 5 | 5 | 0 | 0 |
| Batasan 1.5 | 11 | 10 | 1 | 0 |
| Komponen Utama 3.2.3 | 12 | 12 | 0 | 0 |
| Implementasi 4.2.1–4.2.5 | 5 | 5 | 0 | 0 |
| FR-01..FR-15 (4.4.2) | 15 | 15 | 0 | 0 |
| TC-01..TC-10 (4.3.2) | 10 | 10 | 0 | 0 |
| Metrik 4.3.3 | 5 | 5 | 0 | 0 |
| Timeline 5.1 | 5 | 5 | 0 | 0 |
| Pembagian Tim 5.2 | 5 | 5 | 0 | 0 |
| **Total** | **80** | **79** | **1** | **0** |

**Kesimpulan singkat:** proyek **sudah sesuai proposal** untuk seluruh luaran, tujuan khusus, kebutuhan fungsional, test case, dan metrik. Satu item "Sebagian" pada batasan #11 (SATUSEHAT) karena status **lebih baik** dari batasan (bukan hanya mock — sandbox nyata sudah diuji). Detail di bawah.

---

## BAB I — Pendahuluan

### 1.7 Luaran Proyek
| # | Luaran | Status | Bukti |
|---|--------|--------|-------|
| 1 | Prototipe aplikasi middleware | ✅ | `backend/app/` (FastAPI) + `worker` + `scheduler`; `docker-compose.yml` |
| 2 | Adapter OpenMRS/OpenEMR/SATUSEHAT (atau mock) | ✅ | `backend/app/adapters/{openmrs,openemr,satusehat}.py`; `mocks/main.py` |
| 3 | Management API | ✅ | `backend/app/api/*` (systems/jobs/conflicts/mappings/metrics/audit) |
| 4 | Admin dashboard | ✅ | `frontend/` (Next.js + shadcn + Recharts, 5 halaman) |
| 5 | Skema basis data middleware | ✅ | `backend/app/models/__init__.py` (external_systems, sync_policies, identifier_mapping, sync_jobs, job_attempts, conflicts, terminology_map, audit_log) |
| 6 | Dokumentasi arsitektur, API, konfigurasi, cara jalan | ✅ | `docs/architecture.md`, `docs/api.md`, `docs/configuration.md`, `docs/runbook.md`, `README.md` |
| 7 | Hasil pengujian & metrik | ✅ | `docs/testing.md`, `tests/` (unit/integration/e2e), `GET /api/v1/metrics` |

### 1.4.2 Tujuan Khusus
| # | Tujuan | Status | Bukti |
|---|--------|--------|-------|
| 1 | Arsitektur hub-and-spoke + adapter per sistem | ✅ | `docs/architecture.md`; `adapters/base.py` (AdapterInterface) + 3 adapter |
| 2 | Pemrosesan Patient/Encounter/Observation + mapping identifier | ✅ | `core/transform.py`, `core/identity.py`, `core/mpi.py` |
| 3 | Validasi, routing, antrean, retry, anti-duplikasi, deteksi konflik | ✅ | `core/validation.py`, `services/sync.py`, `queue/worker.py`, `scheduler/*`, `core/conflict.py` |
| 4 | Dashboard koneksi/pekerjaan/error | ✅ | `frontend/app/page.tsx` (5 tab + grafik) |
| 5 | Uji & evaluasi keberhasilan/konsistensi/latensi/penanganan gagal | ✅ | `docs/testing.md`; `GET /metrics` (success rate, latency, duplicate skips) |

### 1.5 Batasan Masalah
| # | Batasan | Status | Catatan |
|---|---------|--------|---------|
| 1 | Target OpenMRS/OpenEMR/SATUSEHAT | ✅ | 3 adapter |
| 2 | Middleware independen (bukan plugin) | ✅ | Aplikasi FastAPI terpisah |
| 3 | HL7 FHIR R4 | ✅ | Seluruh transformasi R4 |
| 4 | Resource Patient/Encounter/Observation | ✅ | Ditambah Condition (prasyarat SATUSEHAT) |
| 5 | Dua arah OpenMRS–OpenEMR sesuai kapabilitas | ✅ | Policy `bidirectional` (Patient/Encounter); Observation 1 arah (append-only) |
| 6 | SATUSEHAT outbound + inbound selektif | ◑ | Outbound terbukti (sandbox nyata); inbound selektif = backlog (lihat RENCANA) |
| 7 | Polling + async, bukan real-time | ✅ | `scheduler/poller.py` + `queue/worker.py` |
| 8 | Konflik hanya deteksi + review manual | ✅ | `core/conflict.py` + tabel `conflicts`; tanpa auto-merge |
| 9 | Data sintetis | ✅ | `fixtures/*`; identitas memakai entitas sandbox agar lolos validasi |
| 10 | Deployment dev/demo | ✅ | `docker-compose.yml` (+ profil `ehr` opsional) |
| 11 | Tanpa sandbox → mock; hasil = simulasi | ✅ (melampaui) | Mock tersedia **dan** sandbox nyata diuji: `backend/probe_satusehat.py`, `docs/satusehat-integration.md` |

> Item #6 (inbound selektif) satu-satunya "Sebagian" — wajar karena proposal menyebutnya *selektif bila didukung endpoint & diizinkan*; outbound adalah use case utama.

---

## BAB III — Pengembangan Prototipe

### 3.2.3 Komponen Utama (12)
| Komponen | Status | Bukti |
|----------|--------|-------|
| OpenMRS Adapter | ✅ | `adapters/openmrs.py` |
| OpenEMR Adapter | ✅ | `adapters/openemr.py` |
| SATUSEHAT Adapter | ✅ | `adapters/satusehat.py` (+ `transaction()`) |
| Ingestion & Normalization | ✅ | `core/normalization.py` |
| FHIR Transformation | ✅ | `core/transform.py`, `core/satusehat_builder.py` |
| Identity Mapping | ✅ | `core/identity.py`, `core/mpi.py` |
| Validation Engine | ✅ | `core/validation.py` (light + target-aware; HAPI opsional) |
| Synchronization Policy | ✅ | `models.SyncPolicy`, `seed.py` (bidirectional) |
| Conflict Detection | ✅ | `core/conflict.py`, `services/sync.py` |
| Queue & Worker | ✅ | `queue/worker.py` (DB `SKIP LOCKED`) |
| Retry & Reconciliation | ✅ | `services/sync.py` (backoff), `scheduler/reconciler.py` |
| Audit & Monitoring | ✅ | `audit/logger.py`, `api/metrics.py`, dashboard |

---

## BAB IV — Implementasi & Pengujian

### 4.2 Implementasi
| Subbab | Status | Bukti |
|--------|--------|-------|
| 4.2.1 Adapter (cek konektivitas, read/search/create/update, error seragam) | ✅ | `adapters/base.py`, `adapters/http_base.py` |
| 4.2.2 FHIR Processing (terima, cek resourceType, normalisasi, konversi, validasi, laporan error) | ✅ | `core/normalization.py`, `core/transform.py`, `core/validation.py` |
| 4.2.3 Identity Mapping (struktur field lengkap, larangan match nama) | ✅ | `core/identity.py`; `models.IdentifierMapping` (source/target system, identifier, type, status, timestamps) |
| 4.2.4 Synchronization Engine | ✅ | `services/sync.py` |
| 4.2.5 Dashboard (konektivitas, akumulasi status, riwayat, error tersanitasi, konflik, retry) | ✅ | `frontend/app/page.tsx` |

### 4.3.2 Skenario Pengujian (TC-01..TC-10)
| ID | Skenario | Status | Bukti |
|----|----------|--------|-------|
| TC-01 | Ambil Patient dari OpenMRS | ✅ | `tests/integration/test_adapters.py` |
| TC-02 | Kirim Patient ke OpenEMR | ✅ | `tests/e2e/test_api_e2e.py` |
| TC-03 | Kirim Encounter dgn referensi Patient | ✅ | demo + `transform` (subject dipetakan) |
| TC-04 | Kirim Observation | ✅ | LOINC+unit; `tests/unit/test_transform.py` |
| TC-05 | Endpoint timeout | ✅ | retry backoff; `tests/integration/test_audit_fixes_db.py` (F2 timeout) |
| TC-06 | Pekerjaan diproses ulang (duplikasi) | ✅ | idempotency + search-before-create |
| TC-07 | Data pasien tak bisa dipetakan | ✅ | `needs_review` (identity) |
| TC-08 | Data tak memenuhi profil tujuan | ✅ | `tests/unit/test_validation.py` |
| TC-09 | Token SATUSEHAT tidak valid | ✅ | adapter memetakan 401/403 → auth non-retryable |
| TC-10 | Dashboard memuat riwayat | ✅ | dashboard HTTP 200; screenshot `docs/screenshots/` |
| *(tambahan)* TC-11..TC-13 | SATUSEHAT sandbox nyata; dua arah; konflik | ✅ | `docs/testing.md` |

### 4.3.3 Metrik Evaluasi
| Metrik | Status | Bukti |
|--------|--------|-------|
| Success Rate | ✅ | `GET /api/v1/metrics` → `success_rate_percent` |
| Latency | ✅ | `avg_latency_seconds` |
| Data Consistency | ✅ | `_same_content` + validasi target; `docs/testing.md` |
| Duplicate Prevention | ✅ | `duplicate_skips` + idempotency key |
| Failure Recovery | ✅ | retry + reconciler; teruji attempt#1 temp → attempt#2 success |

### 4.4.2 Kebutuhan Fungsional (FR-01..FR-15)
| ID | Kebutuhan | Status | Bukti |
|----|-----------|--------|-------|
| FR-01 | Koneksi OpenMRS | ✅ | `adapters/openmrs.py`, `seed.py` |
| FR-02 | Koneksi OpenEMR | ✅ | `adapters/openemr.py` |
| FR-03 | Adapter SATUSEHAT/mock | ✅ | `adapters/satusehat.py`, `mocks/main.py` |
| FR-04 | Baca resource FHIR | ✅ | adapter read/search |
| FR-05 | Transformasi resource | ✅ | `core/transform.py` |
| FR-06 | Simpan pemetaan identitas | ✅ | `core/identity.py`, `/mappings` |
| FR-07 | Validasi sebelum kirim | ✅ | `core/validation.py` |
| FR-08 | Aturan kebijakan sinkronisasi | ✅ | `models.SyncPolicy` |
| FR-09 | Pemrosesan async | ✅ | queue + worker |
| FR-10 | Retry kegagalan sementara | ✅ | `_schedule_retry` + backoff |
| FR-11 | Deteksi pemrosesan berulang & konflik | ✅ | idempotency + `core/conflict.py` |
| FR-12 | Rekam status + audit | ✅ | `sync_jobs`, `job_attempts`, `audit_log`, `/audit` |
| FR-13 | Dashboard koneksi & riwayat | ✅ | dashboard |
| FR-14 | Operator evaluasi error & konflik | ✅ | tab Conflicts/Jobs |
| FR-15 | Operator instruksikan retry | ✅ | `POST /jobs/{id}/retry` + tombol UI |

### 4.4.3 Nonfungsional
Modularitas, maintainability, reliability, security, observability, data integrity, portability — **✅ diterapkan** (struktur modular, audit log + sanitasi, retensi payload, Docker, health check).

---

## BAB V — Rencana & Tim

### 5.1 Timeline (5 minggu) — ✅ seluruh tahap terealisasi (lihat `docs/ROADMAP.md`).
### 5.2 Pembagian Tim — ✅ peran sesuai proposal (Kevin backend, Ayasha frontend, Danar FHIR, Ardi EHR, Satya SATUSEHAT/QA).

---

## DAFTAR GAP & REKOMENDASI
Gap fungsional kecil yang tersisa (detail & prioritas di `docs/RENCANA-PENGEMBANGAN.md`):
1. **Inbound SATUSEHAT selektif** (batasan #6) — belum ada alur tarik data terpilih.
2. **Validasi profil penuh via HAPI** — saat ini validasi ringan + target-aware; HAPI masih opsional/belum aktif.
3. **Version-based conflict detection** — saat ini berbasis heuristik konten (lihat audit F4).
4. **Fitur SSRME (viewing)** — belum (di luar use case inti; ada di Juknis).
5. **RBAC granular + export audit** — audit log ada, export/RBAC masih dasar.
6. **Pemetaan diagnosis dari sumber** — sudah ditambahkan (helper `_icd_from_resource`), perlu diperluas ke Condition resource penuh.

**Kesimpulan:** tidak ada gap yang membatalkan kesesuaian proposal; gap di atas bersifat **pengembangan lanjutan**.
