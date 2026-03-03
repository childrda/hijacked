"""Disable-account action: containment + record; email notification logic."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Detection, Action
from app.actions.containment import run_containment, result_from_details
from app.detect.rules import get_label


async def disable_account(
    db: Session,
    alert_ids: list[int],
    reason: str = "",
) -> dict[str, Any]:
    """
    For each detection: run containment (or propose), record action, update detection status.
    If ACTION_FLAG=false, mode=PROPOSED and we don't call Directory API.
    """
    settings = get_settings()
    mode = "TAKEN" if settings.action_flag else "PROPOSED"
    results = []
    for det_id in alert_ids:
        det = db.get(Detection, det_id)
        if not det or det.status != "OPEN":
            continue
        target = det.target_email
        details = run_containment(db, target, det_id, mode=mode)
        result = result_from_details(details)
        act = Action(
            detection_id=det_id,
            target_email=target,
            action_type="DISABLE_ACCOUNT",
            mode=mode,
            result=result,
            details_json=details,
        )
        db.add(act)
        det.status = "ACTIONED"
        det.updated_at = datetime.now(timezone.utc)
        results.append({"detection_id": det_id, "target_email": target, "result": result})
    db.commit()
    return {"actions": results, "mode": mode}


def build_detection_email(
    detection: Detection,
    action_taken: bool,
    proposed_or_failed: str,
    ui_base_url: str,
) -> tuple[str, str]:
    """Subject and body (text) for detection notification email."""
    risk = detection.risk_level or "MEDIUM"
    subject = f"[{risk}] Workspace Security Alert: {detection.target_email} (Score {detection.score})"
    lines = [
        f"User: {detection.target_email}",
        f"Score: {detection.score}",
        f"Risk: {detection.risk_level}",
        f"Time window: {detection.window_start} - {detection.window_end}",
        f"Detection ID: {detection.id}",
        "",
        "--- Detected Changes ---",
    ]
    for h in (detection.rule_hits_json or []):
        rule = h.get("rule") or ""
        params = h.get("parameters") or {}
        label = get_label(rule) or rule
        lines.append(f" - {label}: {params}")
    mass_message_ids: list[str] = []
    for h in (detection.rule_hits_json or []):
        if h.get("rule") in ("mass_outbound_single", "mass_outbound_burst"):
            msg_id = (h.get("parameters") or {}).get("message_id")
            if msg_id:
                mass_message_ids.append(str(msg_id))
    lines.extend(["", "--- Correlated Signals ---", "(IP/geo/user-agent from raw events)"])
    lines.extend(["", f"--- {proposed_or_failed} ---"])
    if action_taken:
        lines.append("Containment was executed: user suspended, sign-out, tokens revoked.")
    else:
        lines.append("Proposed action: disable account and revoke sessions (ACTION_FLAG=false or action failed).")
    if mass_message_ids:
        lines.append("")
        for msg_id in sorted(set(mass_message_ids)):
            lines.append(
                f"Guidance: Search Gmail logs for Message-ID {msg_id} and remove from inboxes if needed."
            )
    lines.append("")
    lines.append(f"View in UI: {ui_base_url.rstrip('/')}/alerts/{detection.id}")
    body = "\n".join(lines)
    return subject, body


def should_send_detection_email(detection: Detection) -> bool:
    """Re-email only if: new, or risk escalated, or score +20, or >=12h since last."""
    if detection.status != "OPEN":
        return False
    threshold = get_settings().severity_threshold
    if detection.score < threshold:
        return False
    if detection.notified_at is None:
        return True
    # Re-notify conditions
    if detection.last_notified_score is not None and detection.score >= detection.last_notified_score + 20:
        return True
    level_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    last_level = "LOW"
    if detection.last_notified_score is not None:
        if detection.last_notified_score >= 100:
            last_level = "CRITICAL"
        elif detection.last_notified_score >= 70:
            last_level = "HIGH"
        elif detection.last_notified_score >= 40:
            last_level = "MEDIUM"
    if level_order.get(detection.risk_level, 0) > level_order.get(last_level, 0):
        return True
    if (datetime.now(timezone.utc) - detection.notified_at) >= timedelta(hours=12):
        return True
    return False


def record_email_failure(db: Session, detection_id: int | None, target_email: str, error: str) -> None:
    db.add(Action(
        detection_id=detection_id,
        target_email=target_email,
        action_type="EMAIL_NOTIFY",
        mode="TAKEN",
        result="FAILED",
        details_json={"error": error},
    ))
    db.commit()


async def send_detection_notification(
    db: Session,
    detection_id: int,
    action_taken: bool,
) -> bool:
    """
    Send email for this detection. action_taken = True if we ran containment.
    Updates notified_at on success; records EMAIL_NOTIFY FAILED on failure.
    Returns True if sent, False if failed (and recorded).
    """
    from app.notifier import get_notifier

    det = db.get(Detection, detection_id)
    if not det:
        return False
    settings = get_settings()
    if det.score < settings.severity_threshold:
        return False
    proposed = "Proposed Action" if not action_taken else "Action Taken"
    subject, body = build_detection_email(det, action_taken, proposed, settings.ui_base_url)
    try:
        notifier = get_notifier()
        await notifier.send(settings.support_email, subject, body)
        det.notified_at = datetime.now(timezone.utc)
        det.notification_count = (det.notification_count or 0) + 1
        det.last_notified_score = det.score
        db.add(Action(
            detection_id=detection_id,
            target_email=det.target_email,
            action_type="EMAIL_NOTIFY",
            mode="TAKEN",
            result="SUCCESS",
            details_json={"subject": subject},
        ))
        db.commit()
        return True
    except Exception as e:
        record_email_failure(db, detection_id, det.target_email, str(e))
        return False
