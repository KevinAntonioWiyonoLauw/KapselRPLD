"""Unit tests: security headers + HTTPS redirect middleware (#17)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.middleware.https import HTTPSRedirectMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware


def _app_with_security():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    @app.get("/docs")
    def docs():
        return {"docs": True}

    return app


def test_security_headers_present_on_api():
    client = TestClient(_app_with_security())
    r = client.get("/api/ping")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in r.headers["content-security-policy"]


def test_csp_skipped_for_docs():
    client = TestClient(_app_with_security())
    r = client.get("/docs")
    assert "content-security-policy" not in {k.lower() for k in r.headers.keys()}


def test_hsts_only_over_https(monkeypatch):
    monkeypatch.setattr(settings, "hsts_max_age", 123, raising=False)
    client = TestClient(_app_with_security())
    r_http = client.get("/api/ping")
    assert "strict-transport-security" not in {k.lower() for k in r_http.headers.keys()}
    r_https = client.get("/api/ping", headers={"x-forwarded-proto": "https"})
    assert "strict-transport-security" in {k.lower() for k in r_https.headers.keys()}


def test_https_redirect_when_forced(monkeypatch):
    monkeypatch.setattr(settings, "force_https", True, raising=False)
    app = FastAPI()
    app.add_middleware(HTTPSRedirectMiddleware)

    @app.get("/api/x")
    def x():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    client = TestClient(app, follow_redirects=False)
    r = client.get("/api/x")
    assert r.status_code == 307
    assert r.headers["location"].startswith("https://")
    # health is exempt from redirect
    assert client.get("/health").status_code == 200
