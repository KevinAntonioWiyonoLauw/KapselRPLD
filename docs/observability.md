# Observability

Structured logging + Prometheus metrics (#16).

## Structured logging
- `LOG_FORMAT=text` (default): human-readable logs for development.
- `LOG_FORMAT=json`: one JSON object per line (`ts`, `level`, `logger`, `msg`, plus
  whitelisted `extra` fields and exception traces). Cocok untuk Loki/ELK/CloudWatch.
- Diterapkan ke backend, worker, dan scheduler lewat `app.logging_setup.configure_logging()`.

Contoh (json):
```json
{"ts":"2026-11-21T08:53:33+0000","level":"INFO","logger":"api","msg":"database initialized"}
```

## Prometheus metrics
Scrape target: **`GET /api/v1/metrics/prometheus`** (tanpa auth, untuk scrape internal).
Dua sumber digabung:
- **Gauge dari DB** (benar lintas worker, di-refresh saat scrape):
  - `kapsel_jobs_total_db` total job
  - `kapsel_jobs_by_status{status}` job per status
  - `kapsel_conflicts_pending` konflik menunggu review
  - `kapsel_duplicate_skips` idempotent skip
  - `kapsel_success_rate_percent` success rate
- **Counter in-process** (throughput/latency per worker):
  - `kapsel_jobs_total{resource_type,target,status}`
  - `kapsel_job_duration_seconds_total{resource_type,target}`

Nonaktifkan dengan `METRICS_ENABLED=false` (endpoint 404).

## Contoh scrape config (Prometheus)
```yaml
scrape_configs:
  - job_name: kapselrpld
    metrics_path: /api/v1/metrics/prometheus
    static_configs:
      - targets: ["backend:8000"]
```
