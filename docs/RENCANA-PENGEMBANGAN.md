# RENCANA PENGEMBANGAN — Middleware FHIR
## Backlog fitur terprioritas untuk melengkapi & mengembangkan (mengacu Proposal)

> Legenda: **P0** wajib untuk demo/produksi · **P1** penting · **P2** pengembangan lanjutan.
> Effort: **S** (<0.5 hari) · **M** (0.5–2 hari) · **L** (>2 hari).
> Status: ✅ selesai · ◑ sebagian · ✗ belum.

| # | Fitur | Alasan (proposal) | Prioritas | Effort | File | Status | Acceptance |
|---|-------|-------------------|-----------|--------|------|--------|-----------|
| 1 | **Pemetaan diagnosis/Condition dari sumber** | SATUSEHAT wajib `Encounter.diagnosis` (RuleNumber 10457) | P0 | S | `core/sync.py:_icd_from_resource` | ✅ | Encounter→SATUSEHAT memakai ICD-10 dari payload bila ada, else default J06.9 |
| 2 | **Auto-provision Encounter (dependency Encounter→Observation, F6)** | Observation SATUSEHAT butuh `encounter` valid | P0 | M | `services/sync.py` | ✅ | Observation tanpa mapping Encounter tetap sukses (Encounter+Condition dibuat otomatis) |
| 3 | **Endpoint Audit + export (FR-12, RBAC/export gap)** | "rekam status + audit", observability | P0 | S | `api/audit.py` | ✅ | `GET /api/v1/audit` + `GET /api/v1/audit/export.csv` |
| 4 | **Aktifkan rate-limit default** (F5) | keamanan API | P1 | S | `.env.example`, `middleware/rate_limit.py` | ✅ | `RATE_LIMIT_PER_MINUTE` default >0, 429 saat lampaui |
| 5 | **Version-based conflict detection (F4)** | konsistensi & konflik terkontrol | P1 | M | `services/sync.py`, `core/conflict.py`, `models` | ✅ | baseline `synced_version` + `synced_target_version`; `classify_version_conflict` (source_newer→update, target_newer→abaikan, both→konflik); konten sebagai fallback |
| 6 | **Multi-Observation per Encounter** | use case klinis nyata | P1 | S | `services/sync.py` | ✅ | beberapa Observation dgn Encounter sama → masing-masing terkirim |
| 7 | **Idempotent Observation (OpenMRS append-only)** | anti-duplikasi | P1 | M | `services/sync.py` | ✅ | kunci dedup `subject`+`code`+`effectiveDateTime` (`_observation_key`); search-before-create mencegah duplikat |
| 8 | **Validasi profil via HAPI FHIR Validator** | "validasi profil yang relevan" (2.5.6) | P1 | M | `core/validation.py` + container | ✗ | validasi StructureDefinition SATUSEHAT via HAPI; flag error |
| 9 | **Inbound SATUSEHAT selektif** (batasan #6) | pengambilan data terpilih | P2 | L | `adapters/satusehat.py`, `scheduler` | ✗ | tarik resource terpilih (GET) berdasarkan policy |
| 10 | **Fitur SSRME (viewing)** | Juknis SSRME (CHLink/SHLink) | P2 | L | modul baru `ssrme/` | ✗ | generate SHLink + tombol buka RME nasional |
| 11 | **RBAC granular + login UI** | keamanan operasional | P2 | M | `api/deps.py`, `frontend` | ✗ | peran (admin/operator/viewer) + kontrol akses |
| 12 | **Grafik metrik tren (time-series)** | observability dashboard | P2 | M | `api/metrics.py`, `frontend` | ◑ | endpoint `/metrics/timeline` ✅; chart di Overview belum |
| 13 | **Backup/restore DB** | keandalan (Bab 3.3.7) | P1 | S | `scripts/backup.ps1` | ✅ | `pg_dump`/restore metadata |
| 14 | **OpenAPI contoh request** | dokumentasi API | P2 | S | `docs/api.md` | ◑ | contoh curl tiap endpoint |

## Urutan eksekusi disarankan
1. **P0** (#1, #2, #3) — sudah ✅.
2. **P1 cepat** (#4, #6, #13) — sudah ✅.
3. **P1 sedang** (#5 version-based conflict, #7 idempotent Obs) — sudah ✅. Sisa #8 HAPI (P1).
4. **P2** (#9 inbound, #10 SSRME, #11 RBAC, #12 tren, #14 docs) — roadmap berikutnya.

## Catatan teknis
- Semua perubahan WAJIB disertai test regresi (`tests/unit`, `tests/integration`, `tests/e2e`).
- Jangan menaruh kredensial di repo; tetap via `.env` (gitignored).
- Perubahan skema (F4: `identifier_mapping.synced_version` + `synced_target_version`) ditambahkan via `create_all` untuk DB baru; untuk DB lama jalankan `ALTER TABLE` (migrasi Alembic dilacak di issue #14).
