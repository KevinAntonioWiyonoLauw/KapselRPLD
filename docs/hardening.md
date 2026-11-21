# Hardening & Deployment (Produksi)

Dokumen ini menjelaskan kontrol keamanan yang sudah ada dan cara mengaktifkannya
saat deploy. Default di `.env.example` sengaja aman untuk **development**.

## 1. Secret management
- Semua kredensial (client secret SATUSEHAT/OpenEMR, password OpenMRS, token admin)
  **hanya** di `.env` yang **di-gitignore**. Tidak pernah di-commit atau di-log.
- `.env.example` hanya memuat placeholder kosong untuk secret.
- Untuk produksi, gunakan secret manager (Docker secrets, Vault, cloud KMS) dan
  suntikkan sebagai environment variable; jangan menyimpan `.env` di server biasa.
- `ADMIN_API_TOKEN` **wajib** diganti dari default. Guard di `app/api/deps.py`
  menolak start melayani endpoint bila token masih default saat `APP_ENV != development`.

## 2. Security headers (otomatis, `SecurityHeadersMiddleware`)
Setiap respons API menyertakan:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Cross-Origin-Opener-Policy: same-origin`
- `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`
  (dikecualikan untuk `/docs`, `/redoc`, `/openapi.json` agar Swagger UI tetap jalan)
- `Strict-Transport-Security` (HSTS) **hanya** saat koneksi HTTPS.

## 3. HTTPS
- Di produksi, terminasi TLS di reverse proxy (nginx/traefik/Caddy) di depan API.
- Set `FORCE_HTTPS=true` agar request HTTP dialihkan (307) ke HTTPS; proxy harus
  mengirim header `X-Forwarded-Proto: https`. Endpoint `/health` dikecualikan.
- `HSTS_MAX_AGE` mengatur durasi HSTS (default 1 tahun).

## 4. Host allowlist
- Set `ALLOWED_HOSTS` (dipisah koma) untuk menolak Host header tak dikenal
  (`TrustedHostMiddleware`), mencegah serangan Host-header/DNS-rebinding.

## 5. Profil proxy TLS (opsional, `docker-compose.prod.yml`)
Untuk demo produksi cepat, jalankan dengan profil `tls` yang menyediakan Caddy
sebagai reverse proxy HTTPS (self-signed untuk lokal):
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile tls up -d
```
Akses API via `https://localhost:8443`.

## 6. Rate limiting
- `RATE_LIMIT_PER_MINUTE` membatasi request `/api/*` per IP (in-memory).
- Untuk multi-instance, gunakan shared store (Redis) — lihat issue #15.

## Verifikasi
```bash
curl -sI http://localhost:8000/health | grep -Ei 'x-|content-security|referrer'
# x-content-type-options: nosniff ; x-frame-options: DENY ; referrer-policy: no-referrer ...
```
