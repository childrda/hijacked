"""Focused tests: dedupe and containment safety."""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, RawEvent, NormalizedEvent, Detection
from app.ingest.poller import _run_detection
from app.services.action_service import disable_account


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Session()


def test_dedupe_alert_creation():
    db = _session()
    now = datetime.now(timezone.utc)
    raw = RawEvent(source="gmail", event_time=now, actor_email="a@example.com", target_email="a@example.com", hash_dedupe="h1")
    db.add(raw)
    db.flush()
    db.add(NormalizedEvent(raw_event_id=raw.id, event_type="external_forwarding_enabled", parameters_json={"destination": "x@evil.com"}))
    db.commit()
    _run_detection(db, window_minutes=60)
    _run_detection(db, window_minutes=60)
    rows = db.query(Detection).all()
    assert len(rows) == 1


def test_containment_respects_action_flag(monkeypatch):
    db = _session()
    det = Detection(
        target_email="victim@example.com",
        window_start=datetime.now(timezone.utc) - timedelta(minutes=5),
        window_end=datetime.now(timezone.utc),
        score=90,
        risk_level="HIGH",
        reasons_json=[],
        rule_hits_json=[{"rule": "external_forwarding_enabled", "parameters": {}}],
        status="NEW",
    )
    db.add(det)
    db.commit()
    monkeypatch.setenv("ACTION_FLAG", "false")
    result = __import__("asyncio").run(disable_account(db, [det.id], reason="test"))
    assert result["mode"] == "PROPOSED"
    assert result["actions"]


def test_containment_blocked_for_closed_contained(monkeypatch):
    db = _session()
    for st in ("CLOSED", "CONTAINED"):
        det = Detection(
            target_email=f"{st.lower()}@example.com",
            window_start=datetime.now(timezone.utc) - timedelta(minutes=5),
            window_end=datetime.now(timezone.utc),
            score=90,
            risk_level="HIGH",
            reasons_json=[],
            rule_hits_json=[{"rule": "external_forwarding_enabled", "parameters": {}}],
            status=st,
        )
        db.add(det)
    db.commit()
    ids = [d.id for d in db.query(Detection).all()]
    monkeypatch.setenv("ACTION_FLAG", "true")
    result = __import__("asyncio").run(disable_account(db, ids, reason="test"))
    assert result["actions"] == []

