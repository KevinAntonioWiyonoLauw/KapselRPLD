"""FastAPI application entrypoint."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import audit, conflicts, health, inbound, jobs, mappings, metrics, ssrme, systems
from app.config import settings
from app.db.session import init_db
from app.middleware.rate_limit import RateLimitMiddleware

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")

app = FastAPI(
    title="Middleware Interoperabilitas HL7 FHIR",
    description="Hub-and-spoke middleware: OpenMRS <-> OpenEMR <-> SATUSEHAT (FHIR R4)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

app.include_router(health.router)
app.include_router(systems.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(conflicts.router, prefix="/api/v1")
app.include_router(mappings.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(inbound.router, prefix="/api/v1")
app.include_router(ssrme.router, prefix="/api/v1")


@app.on_event("startup")
def _startup() -> None:
    try:
        init_db()
        log.info("database initialized")
    except Exception:  # noqa: BLE001
        log.exception("database init failed (will retry on first request)")


@app.get("/")
async def root():
    return {"service": "middleware-fhir", "docs": "/docs", "health": "/health"}
