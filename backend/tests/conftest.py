"""Shared pytest fixtures (DB session for regression tests)."""
import pytest

from app.db.session import SessionLocal, init_db


@pytest.fixture(scope="session")
def _ensure_schema():
    """Ensure the DB schema (incl. additive columns) exists.

    Not autouse: only DB-backed tests (which request ``db_session``) trigger a DB
    connection, so pure unit tests run without any database.
    """
    init_db()


@pytest.fixture
def db_session(_ensure_schema):
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
