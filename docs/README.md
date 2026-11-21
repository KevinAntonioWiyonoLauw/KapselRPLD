# Dokumentasi: Middleware Interoperabilitas HL7 FHIR

Indeks dokumen. Mulai dari `README` di root repo untuk quickstart, lalu pilih dokumen sesuai kebutuhan.

## Untuk pengguna / operator
| Dokumen | Isi |
|---------|-----|
| [../README.md](../README.md) | Ringkasan proyek, quickstart, mode (mock/sandbox/real), struktur repo |
| [PANDUAN-DEMO.md](PANDUAN-DEMO.md) | Skenario demo langkah demi langkah (A–F) + checklist "lulus demo" |
| [runbook.md](runbook.md) | Menjalankan, log, reset data, troubleshooting, EHR asli |

## Untuk pengembang
| Dokumen | Isi |
|---------|-----|
| [architecture.md](architecture.md) | 3 lapisan (adapter / core / processing), alur `process_job`, prinsip kunci |
| [api.md](api.md) | Management API (endpoint, RBAC, contoh curl, status job) |
| [configuration.md](configuration.md) | Semua environment variable + cara beralih ke EHR/SATUSEHAT nyata |
| [testing.md](testing.md) | Suite test (20 unit + 7 integration + 3 e2e = 30) + matriks TC + bukti sandbox |
| [satusehat-integration.md](satusehat-integration.md) | Flow SATUSEHAT R4 nyata, rule number wajib, transaction Bundle |
| [ROADMAP.md](ROADMAP.md) | Peta jalan & status per area |
| [RENCANA-PENGEMBANGAN.md](RENCANA-PENGEMBANGAN.md) | Backlog fitur terprioritas (P0/P1/P2) + acceptance |

## Laporan & audit
| Dokumen | Isi |
|---------|-----|
| [LAPORAN-AKHIR.md](LAPORAN-AKHIR.md) | Laporan akhir (mengikuti struktur proposal, dipetakan ke bukti) |
| [AUDIT-PROPOSAL.md](AUDIT-PROPOSAL.md) | Kesesuaian tiap requirement proposal → implementasi (dengan bukti path) |
| [AUDIT.md](AUDIT.md) | Audit arsitektur (temuan F1–F8 + status perbaikan) |

## Aset
| Path | Isi |
|------|-----|
| [screenshots/](screenshots/) | Tangkapan layar dashboard (6 tab + mobile), dibuat via `scripts/screenshots/shoot.js` |

> Catatan: kredensial (client secret, token) **tidak pernah** ditulis di dokumen. Semua rahasia hanya di `.env` (gitignored).
