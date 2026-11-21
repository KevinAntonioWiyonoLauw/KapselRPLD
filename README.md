# Middleware Interoperabilitas HL7 FHIR

Prototipe middleware **hub-and-spoke** yang menghubungkan **OpenMRS**, **OpenEMR**,
dan **SATUSEHAT** melalui pertukaran **HL7 FHIR R4** untuk resource **Patient,
Encounter, Observation**.

> Middleware berdiri sebagai aplikasi independen dan **tidak menyimpan data klinis** —
> hanya metadata integrasi (identity mapping, status pekerjaan, kebijakan, audit).

## Arsitektur singkat

```
Adapter Layer  →  Interoperability Core  →  Processing & Management Layer
(OpenMRS/OpenEMR/SATUSEHAT)  (transform/validate/identity/policy/conflict)  (queue/worker/retry/API/dashboard)
```

Detail: lihat `docs/architecture.md` dan roadmap di `docs/ROADMAP.md`.

## Quickstart (5 menit)

Prasyarat: Docker + Docker Compose.

```bash
cp .env.example .env          # sesuaikan bila perlu
docker compose up -d --build  # db, mocks, backend, worker, scheduler, dashboard
```

Lalu inisialisasi data sintetis + fixture:

```bash
docker compose exec backend python seed.py
```

Akses:

| Layanan | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| Management API (Swagger) | http://localhost:8000/docs |
| Mock EHR (OpenMRS/OpenEMR) | http://localhost:8100 |
| Mock SATUSEHAT | http://localhost:8200 |

Token admin default ada di `.env` (`ADMIN_API_TOKEN`).

## Demo alur sinkronisasi

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo.ps1
```

Skrip akan meng-enqueue Patient/Encounter/Observation, menunggu worker,
lalu menampilkan status job, metrik, dan data yang mendarat di target.

## Mode

- **mock** (default): EHR & SATUSEHAT disimulasikan service `mocks/`. Cocok untuk dev.
- **sandbox**: SATUSEHAT nyata (staging). Set `SATUSEHAT_MODE=sandbox` + kredensial di `.env`.
- **real**: EHR asli (OpenMRS/OpenEMR). Set `*_MODE=real` + kredensial.

### Uji integrasi SATUSEHAT sandbox (terbukti)
```bash
docker compose exec backend python probe_satusehat.py
```
Menjalankan rantai nyata: Token → Organization → Patient/Practitioner → Location →
Encounter+Condition (transaction Bundle) → Observation. Detail & aturan wajib:
`docs/satusehat-integration.md`. **Kredensial hanya di `.env` (gitignored), bukan di repo.**

## Struktur

```
backend/    FastAPI: adapters, core, queue, scheduler, API, models
frontend/   Next.js dashboard (6 tab, responsif) — shadcn/ui + Tailwind + Recharts
mocks/      Mock EHR + Mock SATUSEHAT (validasi IHS/LOINC)
fixtures/   Data sintetis + prerequisite SATUSEHAT
docs/       Arsitektur, API, konfigurasi, runbook, roadmap
scripts/    Skrip demo/verifikasi
```

## Dokumentasi

- `docs/LAPORAN-AKHIR.md` — laporan akhir (mengikuti struktur proposal)
- `docs/PANDUAN-DEMO.md` — panduan demo langkah-demi-langkah
- `docs/satusehat-integration.md` — flow & aturan integrasi SATUSEHAT
- `docs/architecture.md`, `docs/api.md`, `docs/configuration.md`, `docs/runbook.md`, `docs/testing.md`, `docs/ROADMAP.md`

## Status & batasan

Prototipe untuk **lingkungan pengembangan/demonstrasi**, bukan produksi klinis.
Data uji **sintetis**. Integrasi SATUSEHAT default **mock** (bukan transaksi nyata).
Lihat `docs/ROADMAP.md` untuk progres dan backlog.
