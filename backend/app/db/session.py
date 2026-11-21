"""Database engine, session factory, and declarative base."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


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
    """Create tables (prototype: no Alembic migration yet)."""
    from app import models  # noqa: F401  (register models)

    Base.metadata.create_all(bind=engine)
    _ensure_additive_columns()


def _ensure_additive_columns():
    """Add columns introduced after the first schema version (prototype-grade).

    `create_all` does not ALTER existing tables, so new nullable columns are added
    here idempotently. This will be replaced by Alembic (issue #14).
    """
    from sqlalchemy import inspect, text

    additions = [
        ("sync_policies", "filter_json", "JSONB"),
    ]
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, column, coltype in additions:
            if table not in existing_tables:
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if column not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))
