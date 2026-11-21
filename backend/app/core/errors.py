"""Error normalization helpers.

Turn FHIR ``OperationOutcome`` / fault bodies into a concise, human-readable
message and strip anything that looks like a credential (defence in depth so a
token echoed by a server never ends up in logs or the dashboard).
"""
from __future__ import annotations

import json
import re

# Redact bearer tokens and common secret-bearing JSON/query fields.
_SECRET_PATTERNS = [
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(\"?(?:client_secret|access_token|refresh_token|authorization)\"?\s*[:=]\s*\"?)[^\"&,\s}]+"),
]


def sanitize(text: str) -> str:
    """Mask anything that looks like a credential."""
    if not text:
        return ""
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub(lambda m: m.group(1) + "***", out)
    return out


def summarize_operation_outcome(text: str, limit: int = 300) -> str:
    """Return a concise, sanitized summary of an OperationOutcome / fault body."""
    if not text:
        return ""
    try:
        data = json.loads(text)
    except Exception:  # noqa: BLE001  (non-JSON body)
        return sanitize(text[:limit])

    msgs: list[str] = []
    for issue in (data.get("issue") or [])[:5]:
        txt = (issue.get("details") or {}).get("text") or issue.get("diagnostics")
        if txt:
            expr = issue.get("expression")
            code = issue.get("code")
            suffix = ""
            if code:
                suffix += f" [{code}]"
            if expr:
                suffix += f" {expr}"
            msgs.append(f"{txt}{suffix}")
    fault = data.get("fault")
    if fault:
        msgs.append(fault.get("faultstring", "fault"))
    if data.get("message"):
        msgs.append(str(data["message"]))

    joined = " | ".join(msgs) if msgs else text
    return sanitize(joined[:limit])


def error_message(label: str, detail: str, max_detail: int = 160) -> str:
    """Combine a short category label with a truncated, sanitized detail."""
    d = (detail or "").strip()
    if not d:
        return label
    return f"{label}: {d[:max_detail]}"
