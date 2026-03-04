"""Alert/detection queries and dismiss."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Detection, AuditLog


def get_flagged(
    db: Session,
    status: str = "NEW",
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
        "assigned_to": d.assigned_to,
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
    det.status = "FALSE_POSITIVE"
    det.updated_at = datetime.now(timezone.utc)
    db.commit()
    return True


def bulk_dismiss(db: Session, detection_ids: list[int]) -> int:
    count = 0
    for did in detection_ids:
        det = db.get(Detection, did)
        if det:
            det.status = "FALSE_POSITIVE"
            det.updated_at = datetime.now(timezone.utc)
            count += 1
    db.commit()
    return count


def get_alert_detail(db: Session, detection_id: int) -> dict[str, Any] | None:
    det = db.get(Detection, detection_id)
    if not det:
        return None
    audits = (
        db.query(AuditLog)
        .filter(AuditLog.alert_id == detection_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(50)
        .all()
    )
    timeline = []
    for h in (det.rule_hits_json or []):
        params = h.get("parameters") or {}
        timeline.append(
            {
                "rule": h.get("rule"),
                "when": params.get("event_time"),
                "parameters": params,
            }
        )
    return {
        "id": det.id,
        "target_email": det.target_email,
        "status": det.status,
        "assigned_to": det.assigned_to,
        "notes": det.notes,
        "score": det.score,
        "risk_level": det.risk_level,
        "window_start": det.window_start.isoformat(),
        "window_end": det.window_end.isoformat(),
        "rule_hits": det.rule_hits_json or [],
        "reasons": det.reasons_json or [],
        "timeline": timeline,
        "audit_log": [
            {
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                "actor": a.actor,
                "action": a.action,
                "result": a.result,
                "payload_summary": a.payload_summary,
                "error": a.error,
            }
            for a in audits
        ],
    }


def update_status(db: Session, detection_id: int, status: str) -> bool:
    det = db.get(Detection, detection_id)
    if not det:
        return False
    det.status = status
    det.updated_at = datetime.now(timezone.utc)
    db.commit()
    return True


def assign_alert(db: Session, detection_id: int, assigned_to: str | None) -> bool:
    det = db.get(Detection, detection_id)
    if not det:
        return False
    det.assigned_to = assigned_to
    det.updated_at = datetime.now(timezone.utc)
    db.commit()
    return True


def set_notes(db: Session, detection_id: int, notes: str | None) -> bool:
    det = db.get(Detection, detection_id)
    if not det:
        return False
    det.notes = notes
    det.updated_at = datetime.now(timezone.utc)
    db.commit()
    return True
