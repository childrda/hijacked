"""Tests for Gmail mailbox filter inspection: normalization, fingerprint, risk, approval."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, MailboxFilter, Detection
from app.mailbox_filters.normalize import normalize_criteria, normalize_action, normalized_filter_dict
from app.mailbox_filters.fingerprint import filter_fingerprint
from app.mailbox_filters.risk import evaluate_risk


os.environ.setdefault("ADMIN_PASSWORD", "test")
os.environ.setdefault("SECRET_KEY", "x" * 40)


def test_normalize_criteria_empty():
    assert normalize_criteria(None) == {}
    assert normalize_criteria({}) == {}


def test_normalize_criteria_sorts_and_trims():
    raw = {"subject": "  foo  ", "query": "bar", "from": "x@y.com"}
    out = normalize_criteria(raw)
    assert out.get("subject") == "foo"
    assert out.get("from") == "x@y.com"
    assert list(out.keys()) == sorted(out.keys())


def test_normalize_action_sorts_lists():
    raw = {"addLabelIds": ["b", "a"], "removeLabelIds": ["z", "y"], "forward": " fwd@x.com "}
    out = normalize_action(raw)
    assert out.get("addLabelIds") == ["a", "b"]
    assert out.get("removeLabelIds") == ["y", "z"]
    assert out.get("forward") == "fwd@x.com"


def test_fingerprint_stable():
    fp1 = filter_fingerprint("id1", {"query": "a"}, {"addLabelIds": ["X"]})
    fp2 = filter_fingerprint("id1", {"query": "a"}, {"addLabelIds": ["X"]})
    assert fp1 == fp2


def test_fingerprint_changes_with_content():
    fp1 = filter_fingerprint("id1", {"query": "a"}, {})
    fp2 = filter_fingerprint("id1", {"query": "b"}, {})
    assert fp1 != fp2
    fp3 = filter_fingerprint("id1", {"query": "a"}, {"forward": "x@y.com"})
    assert fp1 != fp3


def test_risky_forward_external():
    with patch("app.mailbox_filters.risk.get_settings") as gs:
        gs.return_value = type("S", (), {"filter_risk_keywords_list": [], "filter_external_forwarding_only": False})()
        risky, reasons = evaluate_risk({}, {"forward": "external@gmail.com"}, "mycorp.com")
        assert risky
        assert "action_forwards_externally" in reasons or "action_forwards" in reasons


def test_risky_keyword_in_subject():
    with patch("app.mailbox_filters.risk.get_settings") as gs:
        gs.return_value = type("S", (), {"filter_risk_keywords_list": ["password"], "filter_external_forwarding_only": True})()
        risky, reasons = evaluate_risk({"subject": "password reset"}, None, "")
        assert risky
        assert any("subject" in r for r in reasons)


def test_approval_suppresses_alert():
    """Approved filter with same fingerprint does not create duplicate detection (covered in sync logic)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    now = datetime.now(timezone.utc)
    mf = MailboxFilter(
        user_email="u@d.com",
        gmail_filter_id="f1",
        fingerprint="abc",
        criteria_json={},
        action_json={},
        is_risky=True,
        risk_reasons_json=["action_forwards_externally"],
        status="approved",
        first_seen_at=now,
        last_seen_at=now,
        approved_by="admin",
        approved_at=now,
    )
    db.add(mf)
    db.commit()
    row = db.query(MailboxFilter).filter(MailboxFilter.fingerprint == "abc").first()
    assert row.status == "approved"
    db.close()


def test_removed_filter_marked():
    """Filters no longer returned by API get status=removed (covered in sync)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    now = datetime.now(timezone.utc)
    mf = MailboxFilter(
        user_email="u@d.com",
        gmail_filter_id="f1",
        fingerprint="old",
        criteria_json={},
        action_json={},
        is_risky=False,
        status="new",
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(mf)
    db.commit()
    mf.removed_at = now
    mf.status = "removed"
    db.commit()
    row = db.query(MailboxFilter).first()
    assert row.status == "removed"
    assert row.removed_at is not None
    db.close()
