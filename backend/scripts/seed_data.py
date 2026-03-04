"""Seed test detections and optional admin user so UI shows sample data without Google."""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal, init_db
from app.db.models import Detection


def seed():
    init_db()
    db = SessionLocal()
    try:
        # Sample detections (last 24h)
        now = datetime.now(timezone.utc)
        samples = [
            {
                "target_email": "alex.brown@example.com",
                "window_start": now - timedelta(minutes=2),
                "window_end": now - timedelta(minutes=2),
                "score": 80,
                "risk_level": "HIGH",
                "reasons_json": ["external_forwarding_enabled"],
                "rule_hits_json": [
                    {"rule": "external_forwarding_enabled", "parameters": {"destination": "user1@external-mx.com"}},
                ],
                "status": "NEW",
            },
            {
                "target_email": "jessica.lee@acme.net",
                "window_start": now - timedelta(minutes=15),
                "window_end": now - timedelta(minutes=15),
                "score": 70,
                "risk_level": "HIGH",
                "reasons_json": ["filter_with_delete"],
                "rule_hits_json": [
                    {"rule": "filter_with_delete", "parameters": {"filters": "DELETED"}},
                ],
                "status": "NEW",
            },
            {
                "target_email": "admin_logins_bot",
                "window_start": now - timedelta(minutes=35),
                "window_end": now - timedelta(minutes=35),
                "score": 60,
                "risk_level": "MEDIUM",
                "reasons_json": ["send_as_alias"],
                "rule_hits_json": [
                    {"rule": "send_as_alias", "parameters": {"alias": "sales@untrusted.co"}},
                ],
                "status": "TRIAGE",
            },
        ]
        for s in samples:
            existing = db.query(Detection).filter(
                Detection.target_email == s["target_email"],
                Detection.window_end >= s["window_start"] - timedelta(hours=1),
            ).first()
            if not existing:
                db.add(Detection(**s))
        db.commit()
        print("Seed done: sample detections.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
