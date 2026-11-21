"""Integration test: Alembic migrations are the schema source of truth (#14).

Runs ``alembic check`` against the live test database; it must report no pending
operations, proving the migration history matches the SQLAlchemy models.
"""
import subprocess


def test_alembic_migrations_match_models():
    r = subprocess.run(["alembic", "check"], capture_output=True, text=True, cwd="/app")
    assert r.returncode == 0, (r.stdout or "") + (r.stderr or "")


def test_alembic_version_table_present():
    from sqlalchemy import create_engine, inspect
    from app.config import settings
    tables = set(inspect(create_engine(settings.database_url)).get_table_names())
    assert "alembic_version" in tables
