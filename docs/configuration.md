# Konfigurasi (Environment Variables)

Semua lewat `.env` (salin dari `.env.example`). **Jangan commit `.env`.**

## Database
| Var | Default | Keterangan |
|-----|---------|-----------|
| `DATABASE_URL` | postgres+psycopg2://... | koneksi Postgres |
| `POSTGRES_DB/USER/PASSWORD` | middleware | kredensial DB |

## App / API
| Var | Default | Keterangan |
|-----|---------|-----------|
| `ADMIN_API_TOKEN` | change_me_admin_token | token bearer Management API |
| `USE_HAPI_VALIDATOR` | false | aktifkan validasi profil HAPI |
| `HAPI_VALIDATOR_URL` | http://hapi-validator:3500 | URL HAPI |

## Adapter (pola sama untuk OPENMRS / OPENEMR / SATUSEHAT)
| Var | Keterangan |
|-----|-----------|
| `<SYS>_ENABLED` | aktif/nonaktif |
| `<SYS>_MODE` | `mock` \| `real`/`sandbox`/`production` |
| `<SYS>_FHIR_BASE_URL` | base URL nyata |
| `<SYS>_AUTH_TYPE` | `basic` (OpenMRS) / `oauth2_client_credentials` |
| `<SYS>_MOCK_URL` | base URL mock |
| `OPENMRS_USERNAME/PASSWORD` | kredensial Basic |
| `OPENEMR_CLIENT_ID/SECRET/TOKEN_URL` | OAuth2 OpenEMR |
| `SATUSEHAT_CLIENT_ID/SECRET/TOKEN_URL` | OAuth2 SATUSEHAT |

## Scheduler / Worker
| Var | Default |
|-----|---------|
| `POLL_INTERVAL_SECONDS` | 30 |
| `RECONCILE_INTERVAL_SECONDS` | 120 |
| `WORKER_POLL_SECONDS` | 5 |
| `RETRY_MAX_ATTEMPTS` | 5 |

## Keamanan / RBAC / CORS
| Var | Default | Keterangan |
|-----|---------|-----------|
| `OPERATOR_API_TOKEN` | (kosong) | token operator; kosong = hanya admin |
| `CORS_ORIGINS` | `http://localhost:3000` | allowlist origin (comma-separated), jangan `*` di produksi |
| `RATE_LIMIT_PER_MINUTE` | 120 | batas request Management API per menit per IP (0 = nonaktif) |
| `PAYLOAD_RETENTION_ON_SUCCESS` | true | hapus payload klinis tersimpan setelah job sukses |

## SATUSEHAT (jalur otomatis) & SSRME
| Var | Keterangan |
|-----|-----------|
| `SATUSEHAT_ORG_ID` | IHS Organization (wajib untuk outbound otomatis) |
| `SATUSEHAT_PRACTITIONER_IHS` | IHS Practitioner default |
| `SATUSEHAT_LOCATION_ID` | Location id (opsional; dibuat otomatis bila kosong) |
| `SATUSEHAT_DEFAULT_ICD10` / `_DISPLAY` | diagnosis default bila sumber tak menyertakan ICD-10 |
| `SSRME_ENABLED` / `SSRME_BASE_URL` | aktifkan & endpoint SSRME (viewing: CHLink/SHLink) |

## Beralih ke EHR / SATUSEHAT nyata

1. Set `OPENMRS_MODE=real`, `OPENEMR_MODE=real`, isi base URL + kredensial.
2. Untuk SATUSEHAT sandbox: `SATUSEHAT_MODE=sandbox`, isi `SATUSEHAT_CLIENT_ID/SECRET`.
3. Pastikan prerequisite (Organization/Location/Practitioner/Patient + IHS) tersedia.
4. Jalankan ulang `docker compose up -d --build backend worker scheduler`.

**Catatan:** integrasi SATUSEHAT default **mock**; hasil mock diklasifikasikan sebagai simulasi.
