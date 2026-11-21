"""Unit tests: observability (metrics + structured logging) (#16)."""
import json
import logging

from app.core import metrics as prom
from app.logging_setup import JsonFormatter


def test_record_job_increments_and_renders():
    prom.record_job("Patient", "openemr", "success", 0.5)
    out = prom.render().decode()
    assert "kapsel_jobs_total" in out
    assert 'target="openemr"' in out
    assert 'status="success"' in out
    assert "kapsel_job_duration_seconds_total" in out


def test_json_formatter_emits_valid_json():
    rec = logging.LogRecord("svc", logging.INFO, __file__, 10, "hello %s", ("world",), None)
    rec.resource_type = "Encounter"
    line = JsonFormatter().format(rec)
    data = json.loads(line)
    assert data["level"] == "INFO"
    assert data["msg"] == "hello world"
    assert data["logger"] == "svc"
    assert data["resource_type"] == "Encounter"
    assert "ts" in data
