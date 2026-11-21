"""Structured logging setup (#16).

``LOG_FORMAT=text`` keeps human-readable logs (dev). ``LOG_FORMAT=json`` emits one
JSON object per line with timestamp, level, logger and message, plus any extra
fields passed via ``logger.info("...", extra={"...": ...})``. This makes logs
machine-parseable for aggregation (Loki/ELK/CloudWatch).
"""
from __future__ import annotations

import json
import logging

from app.config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Include whitelisted extras (avoid dunder/standard attributes).
        for k, v in record.__dict__.items():
            if k not in _STD_ATTRS and not k.startswith("_"):
                try:
                    json.dumps(v)
                    payload[k] = v
                except (TypeError, ValueError):
                    payload[k] = str(v)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_STD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "asctime",
}


def configure_logging() -> None:
    """Install JSON formatting on the root logger when LOG_FORMAT=json."""
    if settings.log_format.lower() != "json":
        return
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(logging.INFO)
