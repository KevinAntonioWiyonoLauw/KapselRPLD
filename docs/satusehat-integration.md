# Integrasi SATUSEHAT (FHIR R4) — Panduan & Temuan

> Dokumen ini merangkum **flow SATUSEHAT yang sudah diverifikasi langsung ke sandbox**
> menggunakan kredensial fasyankes proyek ini. Semua rule number di bawah adalah hasil
> respons validasi SATUSEHAT yang sebenarnya.

## 0. Dua kapabilitas SATUSEHAT (jangan dicampur)

| | (A) Interoperabilitas FHIR R4 | (B) SSRME (Rekam Medis Elektronik) |
|---|---|---|
| Fungsi | **MENGIRIM** data klinis ke SATUSEHAT | **MEMBUKA** RME nasional via link |
| Endpoint | `…/fhir-r4/v1/{Resource}` | `…/ssrme/v2/ntl/chl`, `…/shl` |
| Proyek ini | ✅ dipakai | (fitur viewing, terpisah) |

Middleware ini mengerjakan **(A)**.

## 1. Konfigurasi (`.env`)

```
SATUSEHAT_MODE=sandbox
SATUSEHAT_FHIR_BASE_URL=https://api-satusehat-stg.dto.kemkes.go.id/fhir-r4/v1
SATUSEHAT_TOKEN_URL=https://api-satusehat-stg.dto.kemkes.go.id/oauth2/v1/accesstoken?grant_type=client_credentials
SATUSEHAT_CLIENT_ID=<dari SSP>
SATUSEHAT_CLIENT_SECRET=<dari SSP>       # JANGAN commit
SATUSEHAT_ORG_ID=<Organization IHS id>   # dari SSP / Kode Akses API Sandbox
```
Untuk kembali ke simulasi: `SATUSEHAT_MODE=mock`.

## 2. Autentikasi (OAuth2 client_credentials)

```
POST {TOKEN_URL}                         (grant_type sudah di query string)
Content-Type: application/x-www-form-urlencoded
client_id=...&client_secret=...
→ { "access_token": "...", "token_type": "BearerToken", "expires_in": "..." }
```
Gunakan header `Authorization: Bearer <token>`. **Rate limit**: salah secret maks 1x/menit;
jangan generate token berlebihan.

## 3. Urutan ketergantungan (WAJIB berurutan)

```
Token → Organization (ada) → Patient (IHS) & Practitioner (IHS) → Location
      → Condition + Encounter (transaction Bundle) → Observation
```

## 4. ATURAN WAJIB SATUSEHAT yang ditemukan (rule number nyata)

Ini hasil POST ke sandbox; wajib dipenuhi agar diterima:

| Resource | Field wajib | RuleNumber |
|----------|-------------|-----------|
| Encounter | `serviceProvider` (Reference Organization) | 10124 |
| Encounter | `diagnosis` (Reference Condition) | 10457 |
| Encounter | `statusHistory` (array) | 10122 |
| Encounter | `subject` = `Patient/{IHS}` | — |
| Condition | `encounter` (Reference Encounter) | 10126 |
| Observation | `issued` (datetime) | 10296 |
| Observation | `subject` = `Patient/{IHS}`, `code` LOINC, `status` | — |
| Observation | `encounter` = `Encounter/{uuid}` valid | 10130 |
| Patient | identifier IHS (`https://fhir.kemkes.go.id/id/ihs-number`) | — |

Waktu wajib **UTC+00** (`…+00:00`). Tanggal tidak boleh < 03 Juni 2014.

## 5. Jebakan: circular reference Condition ↔ Encounter

- `Condition.encounter` wajib, tapi Encounter belum ada → `reference target(s) not found`.
- `Encounter.diagnosis` wajib merujuk Condition.
- **Solusi (dipakai):** kirim keduanya dalam **satu transaction Bundle** dengan
  referensi `urn:uuid:...`. SATUSEHAT me-resolve referensi internal dalam transaksi.
  Endpoint: `POST {BASE}` (root, body = Bundle type `transaction`).

## 6. Bentuk payload yang SUDAH TERBUKTI (ringkas)

**Transaction Bundle (Encounter + Condition):**
```json
{ "resourceType":"Bundle","type":"transaction","entry":[
  {"fullUrl":"urn:uuid:ENC","request":{"method":"POST","url":"Encounter"},"resource":{
    "resourceType":"Encounter","status":"finished",
    "identifier":[{"system":"http://sys-ids.kemkes.go.id/encounter/{ORG}","value":"ENC-..."}],
    "statusHistory":[{"status":"arrived","period":{...}},{"status":"in-progress","period":{...}},{"status":"finished","period":{...}}],
    "class":{"system":"http://terminology.hl7.org/CodeSystem/v3-ActCode","code":"AMB","display":"ambulatory"},
    "subject":{"reference":"Patient/{IHS}"},
    "participant":[{"type":[{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/v3-ParticipationType","code":"ATND"}]}],"individual":{"reference":"Practitioner/{IHS}"}}],
    "period":{"start":"...+00:00","end":"...+00:00"},
    "location":[{"location":{"reference":"Location/{LOC}"}}],
    "serviceProvider":{"reference":"Organization/{ORG}"},
    "diagnosis":[{"condition":{"reference":"urn:uuid:COND"},"use":{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/diagnosis-role","code":"DD"}]}}]
  }},
  {"fullUrl":"urn:uuid:COND","request":{"method":"POST","url":"Condition"},"resource":{
    "resourceType":"Condition",
    "clinicalStatus":{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/condition-clinical","code":"active"}]},
    "category":[{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/condition-category","code":"encounter-diagnosis"}]}],
    "code":{"coding":[{"system":"http://hl7.org/fhir/sid/icd-10","code":"J06.9","display":"Acute URI"}]},
    "subject":{"reference":"Patient/{IHS}"},
    "encounter":{"reference":"urn:uuid:ENC"}
  }}
]}
```

**Observation:** lihat `backend/probe_satusehat.py`.

## 6b. Pemetaan diagnosis penuh (multi-Condition, #10)
Encounter dapat memuat **lebih dari satu diagnosis**. Pipeline mengekstrak **semua**
diagnosis dari payload sumber lalu membuat **satu `Condition` per diagnosis** dalam
transaction Bundle, dan `Encounter.diagnosis` merujuk ke tiap Condition:

- Sumber yang didukung (prioritas): `diagnoses: [{code, display}]` (atau `[code, display]`),
  field `diagnosis_code`/`icd10` + `diagnosis_display`, seluruh `reasonCode` ber-sistem
  ICD-10, dan `Condition` tertanam.
- Bila tidak ada diagnosis → fallback ke diagnosis default (`SATUSEHAT_DEFAULT_ICD10`)
  agar Encounter tetap punya minimal satu Condition (wajib).
- Dedup berdasarkan kode; urutan dipertahankan.

Contoh: sumber punya `J06.9` + `E11.9` → bundle berisi `Encounter` + `Condition(J06.9)` +
`Condition(E11.9)`, dan `Encounter.diagnosis` berisi dua referensi.

## 6c. Gate validasi profil sebelum kirim (HAPI, #9)
Ketika `USE_HAPI_VALIDATOR=true`, pipeline **memvalidasi payload terhadap profil
SATUSEHAT SEBELUM mengirim**. Jika gagal, job menjadi `needs_review` dengan daftar
issue dan **tidak ada yang dikirim** (mencegah data invalid masuk sandbox/produksi).

- Validator: `POST {HAPI_VALIDATOR_URL}/validate` dengan body `{"resource": {...}}`,
  mengembalikan `OperationOutcome` (issue kosong = valid).
- Service `hapi-validator` disediakan di `docker-compose.yml` (mock HAPI-style ringan;
  ganti image bila butuh konformansi profil penuh).
- Diuji: payload invalid → `needs_review` (tak terkirim); payload valid → terkirim.

## 6d. Inbound selektif berbasis policy (#11)
Selain tarik manual satu-off (`GET /satusehat/inbound/{resource_type}`), ada **pull
selektif berbasis policy**: pilih resource type + filter, lalu tarik dari SATUSEHAT
dan simpan ke EHR tujuan (mis. OpenMRS/OpenEMR) beserta `IdentifierMapping` sehingga
re-run **idempoten** (tidak menduplikasi).

- Policy disimpan di `sync_policies` dengan `direction="inbound"` dan `filter_json`
  (params pencarian SATUSEHAT, mis. `{"category":"vital-signs"}`).
- API: `POST/GET/DELETE /api/v1/satusehat/inbound-policies`, dan
  `POST /api/v1/satusehat/inbound/pull` untuk menjalankan semua policy inbound sekali.
- Scheduler menjalankan policy inbound tiap `POLL_INTERVAL_SECONDS` (paralel dgn poller).
- Bukti (mock): seed 2 Observation di SATUSEHAT → `pull` ⇒ `created=2`; `pull` kedua
  ⇒ `skipped=2`; target EHR berisi 2 Observation.

## 6e. UX SSRME di dashboard (#12)
Kartu "SSRME: akses RME nasional" pada tab Integrasi memanggil CHLink/SHLink dan
menampilkan hasilnya sebagai aksi nyata (bukan JSON mentah):
- **CHLink** → tombol **"Buka tautan persetujuan"** (buka tab baru ke `verification_url`).
- **SHLink** → tombol **"Buka RME nasional"** (buka tab baru ke `shlink_url`).
- Toggle **Mode darurat (EMERGENCY)** mengirim `type_medical_summary=EMERGENCY`.
- State lengkap: kosong, loading, error, dan sukses; respons mentah tersedia di
  disclosure "Lihat respons mentah".
- Mode mock menyediakan endpoint SSRME (`/fhir-r4/v1/ssrme/chl|shl`) agar alur bisa
  didemokan tanpa kredensial nyata.

## 7. Bukti & cara reproduksi

```bash
# dari root repo (mode sandbox di .env)
docker compose exec backend python probe_satusehat.py
```
Output yang diharapkan (sudah terbukti):
```
[OK] token acquired
[OK] Organization … -> 200
[OK] Patient/100000030009 -> 200
[OK] Practitioner/10009880010 -> 200
[OK] Location …
    201 Created …/Encounter/…/_history/…
    201 Created …/Condition/…/_history/…
[OK] Encounter+Condition created; Encounter=…
[OK] Observation created id=…
```

Entitas sandbox nyata yang dipakai:
- Organization: `<SATUSEHAT_ORG_ID>` (mis. "STAGING …")
- Patient IHS: `100000030009` (contoh docs; bisa diganti `SS_PATIENT_IHS`)
- Practitioner IHS: `10009880010` (dummy sandbox; `SS_PRACTITIONER_IHS`)
- Location: dibuat otomatis bila belum ada.

## 8. Status & langkah lanjut

- ✅ Terbukti: seluruh rantai interoperabilitas ke sandbox nyata (via `probe_satusehat.py`).
- ✅ `SatusehatAdapter.transaction()` tersedia untuk mengirim transaction Bundle.
- ✅ **Jalur OTOMATIS worker → SATUSEHAT berfungsi** (mode `sandbox`/`production`):
  - Encounter → transaction Bundle (Encounter+Condition) → sukses; mapping Encounter disimpan.
  - Observation → dibuat dengan referensi Encounter hasil mapping → sukses.
  - Patient → resolve IHS (verified mapping / MPI by NIK) & verifikasi ada di SATUSEHAT.
  - Modul: `app/core/mpi.py`, `app/core/satusehat_builder.py`, branch `_process_satusehat` di `services/sync.py`.
  - Config: `SATUSEHAT_ORG_ID`, `SATUSEHAT_PRACTITIONER_IHS`, `SATUSEHAT_LOCATION_ID` (opsional), `SATUSEHAT_DEFAULT_ICD10`.
- ⏳ Pengembangan lanjut (opsional): pilihan use case/diagnosis nyata dari data sumber, multi-Observation per Encounter,
  dan tombol SSRME (B) bila diminta.
- 🔒 Secret hanya di `.env` (gitignored); tidak ditulis di dokumen/repo.

## 9. Catatan keamanan
- Client Secret & access token hanya di backend; tidak di log; wajib HTTPS.
- Data uji sandbox ≠ data produksi; hasil diklasifikasikan sebagai simulasi/uji.
