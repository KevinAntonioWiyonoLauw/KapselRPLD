# RBAC & Login (#13)

Tiga peran, dari paling rendah ke paling tinggi:

| Role | Token env | Hak akses |
|------|-----------|-----------|
| **viewer** | `VIEWER_API_TOKEN` | Baca: list/detail jobs, conflicts, mappings, systems, metrics, audit, inbound read |
| **operator** | `OPERATOR_API_TOKEN` | viewer + aksi operasional: retry job, resolve konflik, cek konektivitas, verifikasi mapping, enqueue, SSRME (CHLink/SHLink), inbound pull |
| **admin** | `ADMIN_API_TOKEN` | operator + perubahan konfigurasi: buat/hapus inbound policy, dan semua |

- Token dibandingkan constant-time (`secrets.compare_digest`).
- Role yang token env-nya kosong berarti tidak ada (mis. hanya admin yang aktif).
  Admin token selalu memberi admin.
- `ADMIN_API_TOKEN` default ditolak saat `APP_ENV != development` (guard).

## Endpoint auth
- `POST /api/v1/auth/login` body `{"token": "..."}` → `{"ok": true, "role": "admin|operator|viewer"}`.
- `GET /api/v1/auth/me` (Bearer) → `{"role": ...}`.
- `GET /api/v1/auth/roles` → peran mana yang terkonfigurasi (tanpa secret).

## Login UI (dashboard)
- Kolom token di header + tombol "Muat ulang". Setelah data dimuat, dashboard memanggil
  `/auth/me` dan menampilkan **badge peran** (admin/operator/viewer).
- Tombol aksi (retry, resolve, inbound, SSRME) **dinonaktifkan** untuk viewer.
  (Backend tetap menegakkan otorisasi; UI hanya lapisan kenyamanan.)

## Contoh
```bash
# login
curl -s -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{"token":"demo_viewer_token"}'
# viewer ditolak retry (403); operator diizinkan (200); create policy hanya admin
```

Catatan: rate limit kini **tidak** menghitung preflight OPTIONS dan CORS dipasang
sebagai middleware terluar, sehingga respons 429/redirect tetap membawa header CORS.
