"""Focused tests: auth cookie login/logout and cron auth modes."""
from __future__ import annotations

import os

from fastapi.testclient import TestClient


os.environ["DATABASE_URL"] = "sqlite:///./test_auth_cron.db"
os.environ["APP_ENV"] = "prod"
os.environ["SECRET_KEY"] = "x" * 40
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "password123"
os.environ["RESPONDER_USERS"] = "admin"
os.environ["CRON_AUTH_MODE"] = "apikey"
os.environ["CRON_API_KEY"] = "test-cron-key"

from app.main import app  # noqa: E402
import app.main as app_main  # noqa: E402


def test_auth_cookie_login_logout():
    client = TestClient(app)
    r = client.post("/api/auth/login", json={"username": "admin", "password": "password123"})
    assert r.status_code == 200
    assert "session=" in r.headers.get("set-cookie", "")
    session_cookie = r.cookies.get("session")
    me = client.get("/api/auth/me", cookies={"session": session_cookie})
    assert me.status_code == 200
    out = client.post("/api/auth/logout", cookies={"session": session_cookie})
    assert out.status_code == 200
    me2 = client.get("/api/auth/me")
    assert me2.status_code == 401


def test_cron_auth_apikey_mode(monkeypatch):
    client = TestClient(app)

    async def _fake_poll(*args, **kwargs):
        return True

    monkeypatch.setattr(app_main, "run_poll_and_notify", _fake_poll)
    bad = client.post("/api/cron/poll")
    assert bad.status_code == 401
    good = client.post("/api/cron/poll", headers={"X-CRON-KEY": "test-cron-key"})
    assert good.status_code == 200


def test_cron_auth_oidc_mode(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("CRON_AUTH_MODE", "oidc")
    monkeypatch.setenv("CRON_OIDC_AUDIENCE", "https://example.run.app/api/cron/poll")

    async def _fake_poll(*args, **kwargs):
        return True

    monkeypatch.setattr(app_main, "run_poll_and_notify", _fake_poll)

    def fake_verify(token, request, audience=None):  # noqa: ANN001
        return {"iss": "https://accounts.google.com", "aud": audience}

    from google.oauth2 import id_token

    monkeypatch.setattr(id_token, "verify_oauth2_token", fake_verify)

    good = client.post(
        "/api/cron/poll",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert good.status_code == 200

