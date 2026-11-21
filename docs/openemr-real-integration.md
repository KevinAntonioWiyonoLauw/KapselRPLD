# Integrasi OpenEMR Nyata (FHIR R4 + SMART-on-FHIR)

Dokumen ini merangkum cara menjalankan dan **temuan nyata** saat menghubungkan
middleware ke **OpenEMR sungguhan** (image `openemr/openemr:latest`) melalui FHIR R4.
Semua langkah di bawah sudah **diverifikasi end-to-end** (Patient -> Encounter ->
Observation + baca balik Patient).

> Ringkas: `python probe_openemr.py` (di `backend/`) menghasilkan `PROBE_OPENEMR_OK`.

## 1. Menjalankan OpenEMR (profil `ehr`)

```bash
docker compose -f docker-compose.yml -f docker-compose.ehr.yml --profile ehr up -d openemr-db openemr
```

Boot pertama meng-install skema (bisa beberapa menit). Akses: `http://localhost:8081`
(admin / pass).

## 2. Wajib: aktifkan REST/FHIR API

Secara default API OpenEMR **nonaktif** (token endpoint menjawab `API is disabled`).
Aktifkan global berikut (bisa via UI Administration > Globals, atau SQL):

```bash
docker exec <openemr-db-container> mysql -uroot -proot openemr -e \
 "UPDATE globals SET gl_value='1' WHERE gl_name IN ('rest_api','rest_fhir_api','rest_system_scopes_api');"
```

Helper: `powershell -File scripts/openemr-enable-api.ps1` (idempotent).

## 3. Daftarkan klien OAuth2

```bash
docker exec <openemr-container> bash -c "su -s /bin/sh apache -c \
  'cd /var/www/localhost/htdocs/openemr; php bin/console openemr-dev:register-api-test-client --site=default'"
```
Catat **Client ID** dan **Client Secret** dari output.

## 4. Alur token

- **Password grant (paling mudah untuk lokal/nyata):** aktifkan
  `UPDATE globals SET gl_value='1' WHERE gl_name='oauth_password_grant';`
  lalu isi `.env`: `OPENEMR_USERNAME=admin`, `OPENEMR_PASSWORD=pass`.
  Adapter memakai grant ini bila `OPENEMR_USERNAME` diisi.
- **client_credentials:** didukung, tetapi OpenEMR dapat mewajibkan **JWT client
  assertion** (asymmetric, `private_key_jwt`) tergantung registrasi klien. Untuk
  sistem produksi, daftarkan JWKS publik aplikasi pada klien. (Untuk lokal, password
  grant lebih sederhana.)

## 5. Temuan bentuk data (WAJIB, sudah ditangani kode)

| Hal | Temuan nyata | Penanganan |
|-----|--------------|------------|
| Nama pasien | OpenEMR hanya memetakan `name` dengan `use="official"` ke fname/lname; tanpa itu -> `First/Last Name must not be empty`. | `transform.transform_patient(..., "openemr")` menambahkan `use=official`. |
| Observation | Butuh `Observation.category` untuk routing penyimpanan; tanpa itu -> `Observation.category is required to route a write`. | `transform.transform_observation(..., "openemr")` menambahkan `category=vital-signs`. |
| Observation.encounter | OpenEMR menyimpan Observation sebagai *encounter form*; tanpa referensi Encounter -> `Observation.encounter must reference an Encounter`. | Pipeline menyimpan mapping Encounter (saat Encounter sukses) lalu mengisi `Observation.encounter` dengan target ref (`_encounter_target_ref`). |
| Pencarian Observation | OpenEMR menolak parameter `subject` pada Observation (HTTP 400). | `_search_params(..., "openemr")` mengosongkan pencarian (create-only untuk OpenEMR). |
| Respons create | Bukan resource FHIR standar: Patient `{"pid":2,"uuid":"..."}`, Encounter `{"eid":2,"euuid":"..."}`, Observation `{"uuid":"..."}`. | `OpenEMRAdapter.create()` menormalkan ke `{resourceType, id, meta.lastUpdated}` (id dari `uuid`/`euuid`). |
| Base URL | `/apis/default/fhir` | `OPENEMR_FHIR_BASE_URL` |
| Token URL | `/oauth2/default/token` | `OPENEMR_TOKEN_URL` |

## 6. Konfigurasi `.env`

```
OPENEMR_MODE=real
OPENEMR_FHIR_BASE_URL=http://openemr/apis/default/fhir
OPENEMR_TOKEN_URL=http://openemr/oauth2/default/token
OPENEMR_CLIENT_ID=<dari registrasi>
OPENEMR_CLIENT_SECRET=<dari registrasi>
OPENEMR_USERNAME=admin      # aktifkan password grant
OPENEMR_PASSWORD=pass
```
Restart backend/worker/scheduler setelah mengubah `.env`.

## 7. Membuktikan

```bash
# dari host, di network compose (lihat header probe_openemr.py untuk contoh lengkap)
docker run --rm --network kapselrpld_default \
  -e OPENEMR_MODE=real \
  -e OPENEMR_FHIR_BASE_URL=http://openemr/apis/default/fhir \
  -e OPENEMR_TOKEN_URL=http://openemr/oauth2/default/token \
  -e OPENEMR_CLIENT_ID=... -e OPENEMR_CLIENT_SECRET=... \
  -e OPENEMR_USERNAME=admin -e OPENEMR_PASSWORD=pass \
  -v "$PWD/backend:/app" -w /app kapselrpld-backend:latest python probe_openemr.py
```

Output terverifikasi:
```
[OK] metadata -> 200 CapabilityStatement
[OK] Patient created id=...
[OK] Encounter created id=...
[OK] Observation created id=...
[OK] GET Patient/... -> 200 name=Probe
PROBE_OPENEMR_OK
```

## 8. Catatan OpenMRS (belum dijalankan di sini)

OpenMRS (reference app, JVM) butuh **~2.5-3 GB RAM** tambahan dan boot 5-10 menit.
Adapter `openmrs` sudah ada (Basic auth, `/ws/fhir2/R4`) tetapi uji runtime nyata
belum dilakukan pada mesin dengan resource terbatas. Lihat issue #6.

## 9. Pipeline end-to-end via worker (terbukti)

Selain `probe_openemr.py` (memanggil adapter langsung), jalur **worker sungguhan**
juga diverifikasi dengan `OPENEMR_MODE=real`:

1. Enqueue via Management API: `POST /api/v1/jobs/enqueue` (source `openmrs` -> target `openemr`) untuk Patient, lalu Encounter, lalu Observation (dengan `encounter` merujuk Encounter sumber).
2. Worker memproses ketiganya -> **semua `success`**.
3. Verifikasi di OpenEMR: baris `patient_data` (fname/lname) dibuat, **`form_vitals`** berisi 1 baris (Observation mendarat), dan `identifier_mapping` menyimpan pemetaan **Patient + Encounter**.

Catatan: karena Observation OpenEMR bersifat **create-only** (tanpa pencarian `subject`), dedup untuk OpenEMR mengandalkan `idempotency_key` di sisi middleware; sedangkan target yang mendukung pencarian (mis. OpenMRS) memakai kunci bisnis `subject+code+effective`.
