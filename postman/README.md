# Postman — Demo & Test KapselRPLD

Koleksi Postman untuk mencoba dan **mempresentasikan** alur interoperabilitas
KapselRPLD: **OpenMRS ↔ OpenEMR ↔ SATUSEHAT** melalui adapter middleware.

## Berkas

| Berkas | Isi |
|--------|-----|
| `KapselRPLD.postman_collection.json` | 39 request dalam 7 folder (alur A–F) + test otomatis |
| `KapselRPLD.postman_environment.json` | Environment **Local (mock)** — default demo |
| `KapselRPLD.real-sandbox.postman_environment.json` | Environment **Real (sandbox)** — OpenMRS/OpenEMR/SATUSEHAT nyata |

Import collection + **kedua** environment ke Postman, lalu pilih salah satu di kanan atas.

## Dua environment

| Environment | baseUrl (middleware) | openmrsUrl | openemrUrl | satusehatUrl |
|-------------|----------------------|-----------|-----------|--------------|
| **Local (mock)** | `http://localhost:8000` | `:8100/openmrs` | `:8100/openemr` | `:8200/fhir-r4/v1` |
| **Real (sandbox)** | `http://localhost:8000` | `:8090/openmrs/ws/fhir2/R4` | `:8081/apis/default/fhir` | `api-satusehat-stg…/fhir-r4/v1` |

- **Local (mock)** — demo & test yang **andal/berulang** (offline, tanpa kredensial).
  `.env`: `OPENMRS_MODE=mock`, `OPENEMR_MODE=mock`, `SATUSEHAT_MODE=mock`.
- **Real (sandbox)** — membuktikan integrasi **nyata**.
  `.env`: `OPENMRS_MODE=real`, `OPENEMR_MODE=real`, `SATUSEHAT_MODE=sandbox` + kredensial
  (OpenMRS/OpenEMR real butuh `scripts/openmrs-prepare.ps1` & aktifkan FHIR API OpenEMR).
  Perlu pasien **IHS valid**; **jangan** dijalankan berulang ke SATUSEHAT sandbox
  (membuat resource nyata di staging).

> Panggilan **middleware** (`baseUrl` = `localhost:8000`) **sama** di kedua environment —
> yang berubah hanya **mode di `.env`** (menentukan ke mana middleware meneruskan) dan URL
> sistem langsung (untuk inspeksi). Jadi alur A–F dijalankan identik; hanya backend-nya
> yang bicara ke sistem nyata.

> Akses **langsung** ke `satusehatUrl` di environment Real butuh Bearer token OAuth
> (`client_credentials`). Request B5 (verifikasi Observation di SATUSEHAT) hanya berjalan
> mulus di **mock**; di Real, verifikasi paling praktis lewat response job middleware.


## Prasyarat

```powershell
docker compose up -d --build
docker compose exec backend python seed.py
```

Untuk **demo penuh offline** (tanpa kredensial nyata), set di `.env`:

```
SATUSEHAT_MODE=mock
OPENMRS_MODE=mock
OPENEMR_MODE=mock
```

lalu `docker compose up -d backend worker scheduler`.

> Jika `.env` memakai `SATUSEHAT_MODE=sandbox` / `OPENMRS_MODE=real`, langkah B (ke
> SATUSEHAT) akan memakai sistem **nyata** dan bisa gagal karena IHS/kredensial —
> untuk presentasi yang mulus, gunakan mode mock dulu.

## Otomatis (tanpa ribet)

- **Collection pre-request script** login `admin` otomatis → menyimpan `adminToken`.
  Jadi semua request ber-`Authorization: Bearer {{adminToken}}` langsung jalan.
- Request **Login operator/viewer** menyimpan `operatorToken` / `viewerToken`
  (dipakai folder RBAC).
- Tiap request punya **test** (status code + assert kunci JSON). Jalankan semua lewat
  **Collection Runner** → lihat laporan lulus/gagal.

---

## Konsep alur (yang perlu dipahami saat presentasi)

```
   ┌────────────┐     FHIR R4      ┌──────────────────────────┐     FHIR R4      ┌────────────┐
   │  OpenMRS   │ ──── baca ─────► │      MIDDLEWARE KAPSEL    │ ──── kirim ────► │  OpenEMR   │
   │ (sumber)   │                  │  adapter + transform +    │                  │ (tujuan)   │
   └────────────┘                  │  identity mapping +       │                  └────────────┘
                                   │  validasi + retry/queue   │     FHIR R4      ┌────────────┐
                                   │                          │ ──── kirim ────► │ SATUSEHAT  │
                                   └──────────────────────────┘                  │ (nasional) │
                                                                                 └────────────┘
```

Intinya: **data masuk dari sistem sumber (OpenMRS) → middleware melakukan transformasi
& pemetaan identitas → adapter mengirim ke sistem tujuan (OpenEMR / SATUSEHAT)**.
Middleware **tidak menyimpan data klinis**, hanya metadata integrasi (mapping, status
job, audit).

Yang dibuktikan koleksi ini:
- **A** — middleware membaca Patient dari OpenMRS lalu meneruskannya ke OpenEMR.
- **B** — middleware meneruskan Patient/Encounter/Observation ke **SATUSEHAT**
  (Encounter dikirim sebagai *transaction Bundle* Encounter+Condition; Observation
  dipetakan ke **LOINC** dan subjek **IHS**).
- **C** — idempotency (kirim ulang = dilewati) & deteksi konflik.
- **D** — RBAC 3 peran.
- **E** — inbound selektif dari SATUSEHAT + SSRME.
- **F** — metrik/audit/observability.

> Catatan jujur untuk presentasi: di demo, **pemicu** sinkronisasi adalah endpoint
> `POST /jobs/enqueue` (atau inbound pull dari SATUSEHAT). Pada penerapan nyata,
> pemicu bisa berupa modul/poller di OpenMRS yang memanggil endpoint ini. Middleware
> memproses job lewat worker (poll ±5 dtk).

---

## Naskah demo (urutan klik + yang dikatakan)

### 0 · Health & Auth
- **Health check** → tunjukkan `{"status":"ok"}` (layanan hidup).
- **Login admin/operator/viewer** → tunjukkan tiap peran dapat token berbeda (RBAC).
- **Login password salah** → 401 (keamanan).

### A · Patient OpenMRS → OpenEMR  *(adapter)*
1. **A1** `GET {{openmrsUrl}}/Patient?identifier=MRN-001` → tunjukkan Patient ada di OpenMRS.
2. **A2** `POST /jobs/enqueue` (Patient → openemr) → simpan `job_id`.
3. **A3** `GET /jobs/{{openemrJobId}}` → tunggu sampai `status: success`.
4. **A4** `GET {{openemrUrl}}/Patient?identifier=MRN-001` → Patient **mendarat** di OpenEMR.

> "Middleware membaca data dari OpenMRS, memetakan identitas, lalu meneruskannya ke OpenEMR."

### B · OpenMRS → SATUSEHAT  *(adapter + builder)*
1. **B1** enqueue Patient → satusehat.
2. **B2** enqueue Encounter → satusehat → *(dikirim sebagai transaction Bundle Encounter+Condition)*.
3. **B3** enqueue Observation (vital-signs) → satusehat.
4. **B4** detail job Observation → tunggu `success`.
5. **B5** `GET {{satusehatUrl}}/Observation?code=8310-5` → **Observation dengan LOINC 8310-5
   dan subject `Patient/100000030009` (IHS)**.

> "Adapter kami mengubah konsep `body_temp` menjadi **LOINC 8310-5**, memakai **IHS** sebagai
> subjek, dan mengirim Encounter sebagai **transaction Bundle Encounter+Condition** sesuai
> aturan SATUSEHAT."

### C · Idempotency & Konflik
1. **C1** list jobs.
2. **C2** kirim ulang Patient yang sama → aman (**idempotent**, tidak dobel).
3. **C3** kirim versi berbeda (`version: v2`) → memicu **konflik**.
4. **C4** list konflik → simpan `conflictId`.
5. **C5** resolve konflik.

### D · RBAC
- **D1** viewer boleh baca (200).
- **D2** viewer retry → **403** (ditolak).
- **D3** operator cek konektivitas → 200.
- **D4** operator buat inbound policy → **403** (butuh admin).

### E · Inbound selektif & SSRME
- **E1** baca Patient dari SATUSEHAT by IHS (read-only).
- **E2** buat inbound policy (admin) → simpan `policyId`.
- **E3** list policy. **E4** trigger pull.
- **E5** SSRME CHLink (consent), **E6** SSRME SHLink (akses RME/darurat).

### F · Metrics, Audit, Observability
- **F1** metrics (success rate, latency), **F2** timeline, **F3** Prometheus.
- **F4** audit log, **F5** ekspor CSV, **F6** daftar sistem, **F7** mappings.

---

## Menjalankan sebagai test otomatis

1. **Collection Runner** → pilih collection + environment → **Run**.
2. Untuk hasil paling akurat, jalankan **per folder** (A dulu, lalu B, dst) agar
   variabel `job_id`/`conflictId` sudah terisi.
3. Job diproses worker tiap ±5 dtk: bila request verifikasi (A4/B5) dijalankan terlalu
   cepat, tunggu lalu kirim ulang.

## Troubleshooting

| Gejala | Sebab / solusi |
|--------|----------------|
| 401 semua request | `adminToken` belum terisi — jalankan **Login admin** dulu (atau andalkan pre-request script). |
| Job tetap `pending`/`processing` | Worker belum memproses (poll ±5 dtk). Cek `docker compose ps worker`, tunggu, ulangi detail. |
| B ke SATUSEHAT `needs_review` | `.env` memakai `SATUSEHAT_MODE=sandbox` (sistem nyata) → ganti ke `mock` untuk demo offline. |
| A4/B5 tidak menemukan data | Job belum `success` atau verifikasi dijalankan sebelum worker selesai. |
| `duplicate_skips` di metrics | Normal — bukti idempotency bekerja. |
