# AUDIT — Arsitektur Middleware FHIR
*(Metodologi: agent-architecture-audit, diadaptasi untuk sistem non-agen)*

> **Cakupan & kejujuran metodologi:** Proyek ini **bukan** sistem agen/LLM. Dari 12 layer
> "agent stack", hanya sebagian yang punya **analog** di middleware ini. Layer yang N/A ditandai.
> Temuan diurutkan berdasarkan severity, dengan bukti `file:line`, dan fix plan **code-first**.

## Executive Verdict
- **Overall health:** `demo-ready, belum production-hardened`
- **Primary failure mode:** *hidden repair loop menyamarkan error nyata* — `except Exception`
  yang menandai **bug kode** sebagai `failed_temp` + retry (terbukti: `NameError: version` pernah
  tertangkap & di-retry alih-alih gagal keras).
- **Most urgent fix:** amankan auth/CORS default (token `change_me_admin_token`, `allow_origins=["*"]`).

## Peta 12 Layer → Relevansi
| # | Layer (agent) | Analog di sistem ini | Relevan? |
|---|---------------|----------------------|----------|
| 1 | System prompt | — | N/A |
| 2 | Session history | — | N/A |
| 3 | Long-term memory | tabel `identifier_mapping` (mapping basi) | Sebagian |
| 4 | Distillation | — | N/A |
| 5 | Active recall | — | N/A |
| 6 | Tool selection | routing adapter / sync policy | Ya |
| 7 | Tool execution | eksekusi HTTP adapter | Ya |
| 8 | Tool interpretation | parsing respons/galat adapter | Ya |
| 9 | Answer shaping | `transform.py` (shaping resource) | Ya |
| 10 | Platform rendering | CORS / render dashboard | Ya |
| 11 | **Hidden repair loops** | **retry + reconciler + `except Exception`** | **Ya (kritis)** |
| 12 | Persistence | DB state, `payload_ref` | Ya |

---

## Findings (severity-ranked)

### F1 — HIGH — Auth/CORS default tidak aman
- **Mekanisme:** Management API dijaga `Bearer` yang dibandingkan ke `settings.admin_api_token`
  yang **default `change_me_admin_token`**; CORS `allow_origins=["*"]` + semua method.
- **Evidence:** `backend/app/config.py:13`, `backend/app/api/deps.py:13`, `backend/app/main.py:24`
- **Dampak:** bila `.env` tak diubah / API terekspos, siapa pun bisa memicu retry job & membaca
  mapping/jobs. Untuk demo lokal ok; **berisiko bila di-deploy**.
- **Confidence:** 0.95
- **Fix:** fail-fast bila token default saat `APP_ENV != development`; batasi CORS ke origin
  dashboard; bandingkan token dengan `secrets.compare_digest`.

### F2 — MEDIUM — `except Exception` menyamarkan bug sebagai kegagalan sementara (hidden repair loop)
- **Mekanisme:** `process_job` menangkap **semua** exception → `failed_temp` + retry. Error
  pemrograman (mis. `NameError`) ikut di-retry, menutupi akar masalah.
- **Evidence:** `backend/app/services/sync.py:409`; analog: `adapters/openemr.py:50`,
  `adapters/satusehat.py:51`, `main.py:43`, `queue/worker.py:66`, `scheduler/runner.py:26,33`.
  **Bukti empiris:** saat pengembangan, `Exception: name 'version' is not defined` muncul sebagai
  `failed_temp` & dijadwalkan ulang — bug kode tersamar sebagai gangguan jaringan.
- **Dampak:** debugging lebih lama; job "retry selamanya" untuk bug permanen.
- **Confidence:** 0.9
- **Fix:** tangkap exception spesifik (`httpx.*`, `ValidationError`); biarkan `NameError/TypeError/
  AttributeError` naik → `failed_perm` + log error; hanya kategori jaringan/timeout → `failed_temp`.

### F3 — MEDIUM — Idempotency & pencarian memakai `identifier[0]` (posisional)
- **Mekanisme:** `src_id` dan `_search_params` memakai nilai identifier **pertama** saja.
- **Evidence:** `backend/app/services/sync.py:62`, `backend/app/services/sync.py:105`
- **Dampak:** resource dengan >1 identifier (mis. Patient [IHS, NIK]) bisa salah kunci bila
  identifier identitas bukan yang pertama → risiko tabrakan/duplikasi.
- **Confidence:** 0.75
- **Fix:** pilih identifier berdasarkan **prioritas sistem** (mis. `ihs-number` > `nik` > MRN),
  bukan posisi.

### F4 — MEDIUM — Deteksi konflik berbasis heuristik konten + `source_version="n/a"`
- **Mekanisme:** konflik dipicu bila `_same_content` berbeda; `source_version` sering `"n/a"`;
  `_same_content` Patient hanya banding `name/gender/birthDate`.
- **Evidence:** `backend/app/services/sync.py:363`, `backend/app/services/sync.py:253`
- **Dampak:** (a) false positive bila target menormalisasi field; (b) tak bisa membedakan "siapa
  berubah lebih dulu" karena versi tak terlacak; (c) perubahan hanya pada identifier tak terdeteksi.
- **Confidence:** 0.8
- **Fix:** simpan **versi terakhir tersinkron** per mapping; banding versi (bukan konten);
  gunakan `meta.lastUpdated` sumber yang nyata.

### F5 — LOW — Rate limit default OFF & in-memory per-proses
- **Evidence:** `backend/app/config.py:63`, `backend/app/middleware/rate_limit.py`
- **Dampak:** tanpa batas bila `RATE_LIMIT_PER_MINUTE=0`; tidak akurat saat multi-instance.
- **Fix:** dokumentasikan; aktifkan saat demo terekspos; pindah ke store bersama bila diskalakan.

### F6 — LOW — Ketergantungan urutan Encounter→Observation (SATUSEHAT)
- **Mekanisme:** Observation ke SATUSEHAT butuh mapping Encounter; jika belum ada → `needs_review`.
- **Evidence:** `backend/app/services/sync.py:207`
- **Dampak:** poller bisa meng-enqueue Observation sebelum Encounter → review manual.
- **Fix:** penjadwalan sadar-dependensi, atau auto-buat Encounter bila belum ada.

### F7 — INFO — Mock state in-memory (hilang saat restart)
- **Evidence:** `mocks/main.py` (STORE dict)
- **Dampak:** data mock hilang saat restart. Cukup untuk demo; **dokumentasikan**.

### F8 — INFO — `payload_ref` menyimpan payload klinis sampai sukses
- **Evidence:** `backend/app/services/sync.py:83`; dibersihkan `queue/worker.py` saat sukses.
- **Dampak:** payload klinis tersimpan selama gagal. Sesuai prototipe; pastikan kebijakan retensi.

### Positif (dipertahankan)
- Sanitasi rahasia di audit log (`audit/logger.py:10`); payload dihapus saat sukses
  (`queue/worker.py`); retry **dibatasi** `max_attempts` + backoff (`sync.py`); DB queue
  `FOR UPDATE SKIP LOCKED` (`queue/worker.py`); `/health`; test otomatis 60 lulus.

---

## Architecture Diagnosis
Kegagalan paling relevan dari kerangka agent-audit adalah **layer 11 (hidden repair loops)**:
pola `except Exception → retry` kita berfungsi seperti "repair agent" yang **menyembunyikan**
kegagalan asli (bug kode) sebagai gangguan sementara. Ini bukan bug fungsional tetapi **utang
observability** — persis yang diperingatkan skill: *"jangan biarkan loop perbaikan tersembunyi
menutupi kegagalan nyata."* Layer lain (memory=identity mapping, tool interpretation=adapter,
rendering=CORS) sehat untuk skala prototipe.

## Ordered Fix Plan (code-first)
1. **Amankan auth/CORS** (F1) — guard token default + CORS allowlist + `compare_digest`.
   *Why now:* risiko keamanan tertinggi & murah diperbaiki.
2. **Persempit `except`** (F2) — bedakan error jaringan vs bug; bug → gagal keras + log.
   *Why now:* memperbaiki observability & mencegah retry sia-sia.
3. **Identifier berbasis prioritas sistem** (F3) — perbaiki kunci idempotency/pencarian.
4. **Konflik berbasis versi** (F4) — simpan versi tersinkron, banding versi.
5. **Rate limit & retensi** (F5/F8) — aktifkan saat terekspos, dokumentasikan.
6. **Dependensi Encounter→Observation** (F6) — scheduling sadar-dependensi.

> Status: audit **read-only**; belum ada perubahan kode yang dilakukan.

---

## Status Perbaikan (F1–F3, F5) — SUDAH DITERAPKAN & DIUJI

| # | Temuan | Status | Perubahan | Bukti |
|---|--------|--------|-----------|-------|
| F1 | Auth/CORS default | ✅ FIXED | `config.cors_origins` allowlist; `main.py` pakai allowlist (bukan `*`); `deps.py` `secrets.compare_digest` + fail-closed bila token default di non-dev | live: 401/403/200; CORS `evil.com` ditolak, `localhost:3000` diizinkan |
| F2 | `except Exception` menyamarkan bug | ✅ FIXED | `sync.py`: `_RETRYABLE_EXC` → `failed_temp`+retry; exception lain → `failed_perm` + audit `sync_unhandled` (tanpa retry) | `tests/integration/test_audit_fixes_db.py` (2) |
| F3 | Identifier `[0]` posisional | ✅ FIXED | `sync.py`: `_identifier_value` memilih berdasarkan **prioritas sistem** (IHS>NIK>MRN>PID) | `tests/unit/test_audit_fixes.py` (3) |
| F5 | Rate limit default OFF | ◑ sebagian | Config + middleware tetap ada; **dokumentasikan** untuk diaktifkan saat terekspos (belum diubah default) | — |
| F4 | Konflik berbasis versi | ✅ FIXED | `sync.py`: baseline `synced_version` (sumber) + `synced_target_version` (tujuan) di `identifier_mapping`; `conflict.classify_version_conflict` (source_newer→update, target_newer→abaikan, both→konflik); heuristik konten sebagai fallback | `tests/unit/test_conflict_version.py` (5), `tests/integration/test_conflict_version_db.py` (3) |
| F6 | Dependensi Encounter→Obs | ✅ FIXED | Auto-provision Encounter (+Condition) saat Observation tanpa mapping Encounter | `services/sync.py` (jalur SATUSEHAT) |

**Regresi:** unit **46** · integration **11** · e2e **3** = **60 lulus**. Alur normal (Patient→OpenEMR) tetap `success`.

