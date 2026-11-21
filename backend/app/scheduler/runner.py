"""Scheduler runner: periodic polling + reconciliation via APScheduler.

Run as: python -m app.scheduler.runner
"""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.db.session import SessionLocal, init_db
from app.scheduler.poller import poll_once
from app.scheduler.reconciler import reconcile_once
from app.services.inbound import pull_once

logging.basicConfig(level=logging.INFO, format="%(asctime)s scheduler %(levelname)s %(message)s")
log = logging.getLogger("scheduler")


async def _poll():
    try:
        n = await poll_once()
        if n:
            log.info("poller enqueued %d jobs", n)
    except Exception:  # noqa: BLE001
        log.exception("poll error")


async def _inbound():
    db = SessionLocal()
    try:
        results = await pull_once(db)
        created = sum(r.get("created", 0) for r in results if r.get("ok"))
        if results:
            log.info("inbound policies=%d created=%d", len(results), created)
    except Exception:  # noqa: BLE001
        log.exception("inbound error")
    finally:
        db.close()


def _reconcile():
    try:
        reconcile_once()
    except Exception:  # noqa: BLE001
        log.exception("reconcile error")


async def main() -> None:
    init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_poll, "interval", seconds=settings.poll_interval_seconds)
    scheduler.add_job(_inbound, "interval", seconds=settings.poll_interval_seconds)
    scheduler.add_job(_reconcile, "interval", seconds=settings.reconcile_interval_seconds)
    scheduler.start()
    log.info("scheduler started (poll=%ss, reconcile=%ss)",
             settings.poll_interval_seconds, settings.reconcile_interval_seconds)
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
