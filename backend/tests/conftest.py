"""Shared pytest fixtures (DB session for regression tests)."""
import pytest

from app.db.session import SessionLocal, init_db


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    """Ensure the DB schema (incl. additive columns) exists before DB tests run."""
    init_db()


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
