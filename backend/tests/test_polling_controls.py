"""Focused tests: polling interval, lock overlap, runtime guardrail path."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main as app_main
from app.db.models import Base


def _with_sqlite(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(app_main, "SessionLocal", Session)


def test_internal_loop_respects_interval(monkeypatch):
    calls = {"sleep": None, "poll": 0}

    async def fake_sleep(v):
        calls["sleep"] = v
        raise asyncio.CancelledError()

    async def fake_poll(**kwargs):
        calls["poll"] += 1
        return True

    monkeypatch.setattr(app_main, "get_settings", lambda: SimpleNamespace(
        poll_jitter_seconds=0,
        poll_interval_seconds=7,
    ))
    monkeypatch.setattr(app_main.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(app_main, "run_poll_and_notify", fake_poll)

    try:
        asyncio.run(app_main.internal_poll_loop())
    except asyncio.CancelledError:
        pass
    assert calls["sleep"] == 7


def test_lock_prevents_overlapping_polls(monkeypatch):
    _with_sqlite(monkeypatch)
    monkeypatch.setattr(app_main, "get_settings", lambda: SimpleNamespace(poll_lock_ttl_seconds=600))
    first = app_main._acquire_poll_lock("a")
    second = app_main._acquire_poll_lock("b")
    assert first is True
    assert second is False
    app_main._release_poll_lock("a")


def test_scheduler_endpoint_runtime_guardrail(monkeypatch):
    _with_sqlite(monkeypatch)
    monkeypatch.setattr(app_main, "get_settings", lambda: SimpleNamespace(
        poll_lock_ttl_seconds=600,
        poll_max_runtime_seconds=0,
    ))

    def slow():
        import time
        time.sleep(0.2)

    monkeypatch.setattr(app_main, "_run_poll_and_notify_sync", slow)
    ok = asyncio.run(app_main.run_poll_and_notify(actor="test"))
    assert ok is True

