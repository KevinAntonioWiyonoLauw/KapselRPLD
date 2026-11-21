# Runbook

## Menjalankan
```bash
cp .env.example .env
docker compose up -d --build
docker compose exec backend python seed.py
```

## Melihat status & log
```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f scheduler
```

## Reset data (bersih)
```bash
# hapus job/attempts/conflicts/audit (metadata integrasi)
docker compose exec db psql -U middleware -d middleware \
  -c "TRUNCATE sync_jobs, job_attempts, conflicts, audit_log RESTART IDENTITY CASCADE;"

# reset total termasuk DB volume (HATI-HATI: hapus semua)
docker compose down -v
```

## Menjalankan test
```bash
# unit (tanpa jaringan)
docker run --rm -v "$PWD/backend:/app" -w /app kapselrpld-backend:latest \
  sh -c "pip install -q pytest pytest-asyncio && python -m pytest tests/unit -q"

# integration (butuh stack hidup; jalankan di network compose)
docker run --rm --network kapselrpld_default -v "$PWD/backend:/app" -w /app \
  kapselrpld-backend:latest \
  sh -c "pip install -q pytest pytest-asyncio && python -m pytest tests/integration -q"
```

## Troubleshooting
| Gejala | Penyebab | Solusi |
|--------|---------|--------|
| Port 5432/8000/3000 dipakai | layanan lain | ubah mapping host di `docker-compose.yml` |
| Job `needs_review` | identitas belum termap / validasi gagal | cek `/jobs/{id}`, lengkapi mapping (`/mappings`) |
| Job `failed_temp` berulang | endpoint target down | nyalakan target; retry otomatis via backoff |
| `Gagal memperoleh token` | kredensial OAuth2 salah | cek `*_CLIENT_ID/SECRET` |
| Worker tak memproses | image worker lama | `docker compose build backend && docker compose up -d worker` |
| Data tidak muncul di SATUSEHAT | tanpa IHS/LOINC | pastikan mapping `ihs` + konsep LOINC dikenal |

## Pemeriksaan cepat
```bash
curl -s localhost:8000/health
curl -s -H "Authorization: Bearer change_me_admin_token" localhost:8000/api/v1/metrics
curl -s localhost:8100/openmrs/Patient
curl -s localhost:8200/fhir-r4/v1/Observation
```

## Sinkronisasi dua arah & konflik (OpenMRS <-> OpenEMR)
- Policy dua arah (Patient & Encounter) dibuat oleh `seed.py` (`direction=bidirectional`).
- Poller memindai kedua EHR (OpenMRS & OpenEMR) per policy.
- Jika resource sudah ada di tujuan dengan **nilai berbeda** → job `needs_review` +
  tercatat di tabel `conflicts` (lihat `GET /api/v1/conflicts`).
- Observation: hanya OpenMRS→OpenEMR (OpenMRS append-only).

## Menjalankan EHR asli (opsional, berat)
```bash
docker compose -f docker-compose.yml -f docker-compose.ehr.yml --profile ehr up -d
# OpenMRS: http://localhost:8090  (admin/Admin123)
# OpenEMR: http://localhost:8081  (admin/pass)  -> aktifkan FHIR API di Connectors
# lalu set OPENMRS_MODE=real / OPENEMR_MODE=real + base URL di .env, restart backend/worker/scheduler
```

## Menjalankan semua test
```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-all.ps1
```
(unit 29 · integration 10 · e2e 3 = 42 lulus)
