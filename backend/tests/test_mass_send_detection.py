"""Unit tests for mass outbound email burst detection."""
from datetime import datetime, timedelta, timezone

from app.detect.mass_send import MassSendConfig, generate_mass_send_hits


def _hit(rule: str, t: datetime, params: dict):
    return {"rule": rule, "event_time": t, "parameters": params}


def test_single_message_fanout_threshold():
    now = datetime.now(timezone.utc)
    cfg = MassSendConfig(
        enabled=True,
        recipient_threshold=50,
        window_minutes=10,
        message_threshold=20,
        unique_recipient_threshold=80,
        internal_only_ignore=True,
        allowlist_senders=set(),
        allowlist_subject_keywords=[],
        severity_points_single=70,
        severity_points_burst=60,
        domain="example.com",
    )
    recipients = [f"user{i}@external.org" for i in range(55)]
    hits = [
        _hit(
            "OUTBOUND_MESSAGE_SENT",
            now,
            {"recipients": recipients, "recipient_count": 55, "message_id": "<abc@id>", "subject": "Hello"},
        )
    ]
    out = generate_mass_send_hits("alice@example.com", hits, cfg)
    assert any(h["rule"] == "mass_outbound_single" for h in out)


def test_burst_threshold_window_logic():
    now = datetime.now(timezone.utc)
    cfg = MassSendConfig(
        enabled=True,
        recipient_threshold=500,
        window_minutes=10,
        message_threshold=20,
        unique_recipient_threshold=80,
        internal_only_ignore=False,
        allowlist_senders=set(),
        allowlist_subject_keywords=[],
        severity_points_single=70,
        severity_points_burst=60,
        domain="example.com",
    )
    events = []
    for i in range(20):
        events.append(
            _hit(
                "OUTBOUND_MESSAGE_SENT",
                now - timedelta(minutes=5),
                {"recipients": [f"r{i}@external.org"], "recipient_count": 1, "subject": "FYI"},
            )
        )
    out = generate_mass_send_hits("alice@example.com", events, cfg)
    assert any(h["rule"] == "mass_outbound_burst" for h in out)


def test_allowlist_sender_bypass():
    now = datetime.now(timezone.utc)
    cfg = MassSendConfig(
        enabled=True,
        recipient_threshold=10,
        window_minutes=10,
        message_threshold=5,
        unique_recipient_threshold=10,
        internal_only_ignore=False,
        allowlist_senders={"alerts@example.com"},
        allowlist_subject_keywords=[],
        severity_points_single=70,
        severity_points_burst=60,
        domain="example.com",
    )
    events = [_hit("OUTBOUND_MESSAGE_SENT", now, {"recipients": [f"u{i}@external.org" for i in range(20)]})]
    out = generate_mass_send_hits("alerts@example.com", events, cfg)
    assert out == []


def test_internal_only_ignore_behavior():
    now = datetime.now(timezone.utc)
    cfg = MassSendConfig(
        enabled=True,
        recipient_threshold=10,
        window_minutes=10,
        message_threshold=5,
        unique_recipient_threshold=10,
        internal_only_ignore=True,
        allowlist_senders=set(),
        allowlist_subject_keywords=[],
        severity_points_single=70,
        severity_points_burst=60,
        domain="example.com",
    )
    events = [
        _hit(
            "OUTBOUND_MESSAGE_SENT",
            now,
            {"recipients": [f"u{i}@example.com" for i in range(15)], "recipient_count": 15, "subject": "Internal"},
        )
    ]
    out = generate_mass_send_hits("alice@example.com", events, cfg)
    assert out == []

