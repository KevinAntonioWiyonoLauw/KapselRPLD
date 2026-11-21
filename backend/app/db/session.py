"""Database engine, session factory, and declarative base."""
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# Directory that contains alembic.ini (project root of the backend image: /app).
_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
_BASELINE_REVISION = "84471ae07bd8"


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Apply database migrations via Alembic (replaces create_all + manual ALTER).

    - Serialized with a Postgres advisory lock so multiple containers starting at
      once (backend/worker/scheduler) do not race.
    - Adopts a pre-existing schema (created before Alembic) by stamping the baseline
      revision when the core tables already exist but ``alembic_version`` does not.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_ALEMBIC_INI))
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_lock(778899)"))
        try:
            existing = set(inspect(conn).get_table_names())
            has_version = "alembic_version" in existing
            core_present = {"external_systems", "sync_jobs"}.issubset(existing)
            if not has_version and core_present:
                # Pre-Alembic database: mark baseline as already applied.
                command.stamp(cfg, _BASELINE_REVISION)
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(778899)"))
