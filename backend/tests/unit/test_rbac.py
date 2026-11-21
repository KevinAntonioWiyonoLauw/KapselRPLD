"""Unit tests: RBAC role resolution + hierarchy (#13)."""
import pytest
from fastapi import HTTPException

from app.config import settings
from app.api import deps


@pytest.fixture(autouse=True)
def _tokens(monkeypatch):
    monkeypatch.setattr(settings, "admin_api_token", "ADMIN", raising=False)
    monkeypatch.setattr(settings, "operator_api_token", "OPER", raising=False)
    monkeypatch.setattr(settings, "viewer_api_token", "VIEW", raising=False)
    monkeypatch.setattr(settings, "app_env", "development", raising=False)


def test_resolve_role():
    assert deps.resolve_role("ADMIN") == "admin"
    assert deps.resolve_role("OPER") == "operator"
    assert deps.resolve_role("VIEW") == "viewer"
    assert deps.resolve_role("nope") is None
    assert deps.resolve_role(None) is None


@pytest.mark.asyncio
async def test_require_viewer_allows_all_roles():
    for tok in ("ADMIN", "OPER", "VIEW"):
        role = await deps.require_viewer(authorization=f"Bearer {tok}")
        assert role in ("admin", "operator", "viewer")


@pytest.mark.asyncio
async def test_require_operator_blocks_viewer():
    assert await deps.require_operator(authorization="Bearer OPER") == "operator"
    with pytest.raises(HTTPException) as e:
        await deps.require_operator(authorization="Bearer VIEW")
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_require_admin_only_admin():
    assert await deps.require_admin(authorization="Bearer ADMIN") == "admin"
    with pytest.raises(HTTPException) as e:
        await deps.require_admin(authorization="Bearer OPER")
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_missing_token_401_and_invalid_403():
    with pytest.raises(HTTPException) as e1:
        await deps.current_role(authorization=None)
    assert e1.value.status_code == 401
    with pytest.raises(HTTPException) as e2:
        await deps.current_role(authorization="Bearer bad")
    assert e2.value.status_code == 403


def test_empty_role_token_means_role_absent(monkeypatch):
    monkeypatch.setattr(settings, "viewer_api_token", "", raising=False)
    # Empty viewer token should not authenticate anyone as viewer.
    assert deps.resolve_role("") is None
