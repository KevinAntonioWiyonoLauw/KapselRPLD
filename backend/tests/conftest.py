"""Shared pytest fixtures (DB session for regression tests)."""
import pytest

from app.db.session import SessionLocal


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
