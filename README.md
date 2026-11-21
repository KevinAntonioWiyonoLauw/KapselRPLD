# Middleware Interoperabilitas HL7 FHIR

Middleware **hub-and-spoke** yang menghubungkan **OpenMRS**, **OpenEMR**, dan
**SATUSEHAT** melalui pertukaran **HL7 FHIR R4** untuk resource **Patient,
Encounter, Observation** (dan **Condition** untuk diagnosis).

> Middleware berdiri sebagai aplikasi independen dan **tidak menyimpan data klinis** —
> hanya metadata integrasi (identity mapping, status pekerjaan, kebijakan, audit).
> Versi terkini: **v2.0.0**.

## Arsitektur singkat

```
Adapter Layer  →  Interoperability Core  →  Processing & Management Layer
(OpenMRS/OpenEMR/SATUSEHAT)  (transform/validate/identity/policy/conflict)  (queue/worker/retry/API/dashboard)
```

Detail: lihat `docs/architecture.md` dan roadmap di `docs/ROADMAP.md`.

## Fitur utama

**Integrasi**
- Adapter **OpenMRS**, **OpenEMR**, dan **SATUSEHAT** — mock-aware: dapat dijalankan
  sebagai simulasi (mock) atau koneksi **nyata**.
- Integrasi **nyata**: OpenEMR (OAuth password grant) & OpenMRS (reference-app) end-to-end;
  Patient/Encounter/Observation terverifikasi mendarat di database target.
- **Sinkronisasi dua arah** OpenMRS↔OpenEMR dengan deteksi konflik berbasis versi.

**Kepatuhan SATUSEHAT**
- Multi-diagnosis → **Condition** dalam transaction Bundle.
- **HAPI validator** profile-gate (validasi profil FHIR nyata sebelum kirim).
- **Inbound selektif** (pull read-only / policy berkala) dari SATUSEHAT.
- **SSRME**: CHLink (consent) & SHLink (akses RME/darurat).

**Kesiapan produksi**
- Migrasi skema via **Alembic** (baseline + stamping DB yang sudah ada).
- **Security headers**, HTTPS/host-allowlist, TLS.
- **Observability**: metrik Prometheus + endpoint metrics/timeline.
- **Rate limiting** (memory default, **Redis** opt-in untuk multi-instance).
- **RBAC 3 peran** (admin > operator > viewer) + login UI.

**Kualitas & operasional**
- **Coverage gate** 50% di CI (pytest-cov) + artifact laporan coverage.
- **Playwright e2e + a11y** (axe-core) untuk dashboard.
- **Dashboard** 6 tab, responsif, **dark mode** (persist), pagination, **login form** (username+password, cookie httpOnly).

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

**Login dashboard:** buka http://localhost:3000 → form login (username + password).
Akun demo: `admin`/`admin123`, `operator`/`operator123`, `viewer`/`viewer123`
(diatur via `.env`; sesi cookie httpOnly, opsi "Ingat saya").

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

Rilis **v2.0.0** — siap untuk **lingkungan pengembangan/demonstrasi** dan telah diperkuat
untuk kesiapan produksi (Alembic, security headers/HTTPS, observability, Redis rate-limit, RBAC).
**Bukan** untuk produksi klinis. Data uji **sintetis**. Mode default tetap **mock**; integrasi
nyata (OpenMRS/OpenEMR/SATUSEHAT sandbox) diaktifkan via `.env`. Kredensial hanya di `.env`
(gitignored), tidak pernah masuk repo.

Lihat `docs/ROADMAP.md` untuk status milestone (v1.0–v2.0 selesai).
