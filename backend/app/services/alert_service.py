"""Alert/detection queries and dismiss."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Detection


def get_flagged(
    db: Session,
    status: str = "OPEN",
    window_hours: int = 24,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """List flagged accounts for UI (last N hours, optional search)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    q = (
        db.query(Detection)
        .filter(Detection.window_end >= cutoff)
        .filter(Detection.status == status)
    )
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(Detection.target_email.ilike(term))
    rows = q.order_by(Detection.window_end.desc()).all()
    return [_detection_to_row(r) for r in rows]


def _detection_to_row(d: Detection) -> dict[str, Any]:
    return {
        "id": d.id,
        "target_email": d.target_email,
        "detection_time": d.window_end.isoformat() if d.window_end else None,
        "event_type": _primary_event_type(d),
        "details": _primary_details(d),
        "risk_level": d.risk_level,
        "score": d.score,
        "status": d.status,
    }


def _primary_event_type(d: Detection) -> str:
    hits = d.rule_hits_json or []
    if not hits:
        return "Suspicious activity"
    from app.detect.rules import get_label
    first = hits[0]
    rule = first.get("rule") or first.get("rule_name") or ""
    return get_label(rule) or rule or "Suspicious activity"


def _primary_details(d: Detection) -> str:
    hits = d.rule_hits_json or []
    if not hits:
        return ""
    parts = []
    for h in hits[:3]:
        params = h.get("parameters") or {}
        dest = params.get("destination") or params.get("forward_to") or params.get("alias")
        if dest:
            parts.append(str(dest))
        if h.get("rule") == "mass_outbound_single":
            rc = params.get("recipient_count")
            ic = params.get("internal_count")
            ec = params.get("external_count")
            msg = params.get("message_id")
            subj = params.get("subject")
            mass = f"recipients={rc}, internal/external={ic}/{ec}"
            if subj:
                mass += f", subject={str(subj)[:60]}"
            if msg:
                mass += f", msgid={msg}"
            parts.append(mass)
        if h.get("rule") == "mass_outbound_burst":
            ms = params.get("messages_sent")
            ur = params.get("unique_recipients")
            win = params.get("window_minutes")
            parts.append(f"{ms} messages / {ur} unique recipients in {win}m")
        rule = h.get("rule") or ""
        if rule and not parts:
            parts.append(rule)
    return "; ".join(parts) if parts else ""


def dismiss_alert(db: Session, detection_id: int) -> bool:
    det = db.get(Detection, detection_id)
    if not det:
        return False
    det.status = "DISMISSED"
    det.updated_at = datetime.now(timezone.utc)
    db.commit()
    return True


def bulk_dismiss(db: Session, detection_ids: list[int]) -> int:
    count = 0
    for did in detection_ids:
        det = db.get(Detection, did)
        if det:
            det.status = "DISMISSED"
            det.updated_at = datetime.now(timezone.utc)
            count += 1
    db.commit()
    return count
