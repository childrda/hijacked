"""Disable-account action: containment + record; email notification logic."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Detection, Action
from app.actions.containment import run_containment, result_from_details
from app.detect.rules import get_label
from app.services.audit_service import log_audit

logger = logging.getLogger(__name__)


def _containment_message(details: dict[str, Any], result: str) -> str:
    """Short user-facing message for containment outcome (for API response and logs)."""
    if details.get("proposed"):
        return "Proposed only (no API calls)."
    if details.get("skipped"):
        return details.get("skip_reason") or "Skipped (protected list)."
    suspend = details.get("suspend") or {}
    if suspend.get("skipped") and suspend.get("reason"):
        return str(suspend.get("reason"))  # e.g. "Google Workspace disabled"
    err = details.get("suspend_error") or suspend.get("error")
    if err:
        return str(err)[:500]
    if result == "SUCCESS":
        return "Suspended in Google; sign-out and token revoke attempted."
    return result or "Done"


async def disable_account(
    db: Session,
    alert_ids: list[int],
    reason: str = "",
    *,
    force_execute: bool = False,
) -> dict[str, Any]:
    """
    For each detection: run containment (or propose), record action, update detection status.
    When force_execute=True (responder clicked Disable in UI), always run containment (TAKEN).
    When force_execute=False, ACTION_FLAG controls mode: TAKEN vs PROPOSED (for automatic flows).
    Circuit breaker and cooldown apply when mode=TAKEN.
    """
    settings = get_settings()
    mode = "TAKEN" if (force_execute or settings.action_flag) else "PROPOSED"

    # Circuit breaker: when we would actually run containment, enforce global rate limit
    if mode == "TAKEN" and alert_ids:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.suspension_rate_limit_minutes)
        recent_successes = (
            db.query(Action)
            .filter(Action.action_type == "DISABLE_ACCOUNT")
            .filter(Action.result == "SUCCESS")
            .filter(Action.created_at >= cutoff)
            .count()
        )
        if recent_successes >= settings.suspension_rate_limit_max:
            log_audit(
                db,
                actor="system",
                action="SUSPENSION_RATE_LIMIT_TRIPPED",
                result="fail",
                error="circuit_breaker",
                payload_summary={"recent_successes": recent_successes, "limit": settings.suspension_rate_limit_max},
            )
            raise HTTPException(
                status_code=503,
                detail="Suspension rate limit exceeded; circuit breaker tripped. No further accounts will be suspended until the window clears.",
            )

    results = []
    for det_id in alert_ids:
        det = db.get(Detection, det_id)
        if not det:
            results.append(
                {"detection_id": det_id, "target_email": None, "result": "SKIPPED", "message": "Alert not found."}
            )
            continue
        # Use only DB-backed target_email; reject empty or invalid to prevent injection.
        target_email = (det.target_email or "").strip()
        if not target_email or "@" not in target_email:
            results.append(
                {"detection_id": det_id, "target_email": None, "result": "SKIPPED", "message": "No valid target email."}
            )
            continue
        if det.status in {"CONTAINED", "CLOSED"}:
            results.append(
                {
                    "detection_id": det_id,
                    "target_email": target_email,
                    "result": "SKIPPED",
                    "message": f"Alert is already {det.status}; no action taken.",
                }
            )
            continue
        # Cooldown to avoid repeated disable action on same account.
        recent_action = (
            db.query(Action)
            .filter(Action.target_email == target_email)
            .filter(Action.action_type == "DISABLE_ACCOUNT")
            .filter(Action.created_at >= datetime.now(timezone.utc) - timedelta(minutes=settings.action_cooldown_minutes))
            .first()
        )
        if recent_action:
            results.append(
                {
                    "detection_id": det_id,
                    "target_email": target_email,
                    "result": "FAILED",
                    "error": "cooldown_active",
                    "message": "Cooldown active; wait before retrying.",
                }
            )
            continue
        target = target_email
        time_bucket_start = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        existing = (
            db.query(Action)
            .filter(Action.detection_id == det_id, Action.action_type == "DISABLE_ACCOUNT")
            .first()
        )
        # Skip re-running if we already succeeded; allow retry when previous result was FAILED/SKIPPED (e.g. after fixing config)
        if existing and existing.result == "SUCCESS":
            results.append({"detection_id": det_id, "target_email": target, "result": existing.result, "deduped": True, "message": "Already contained."})
            continue
        if existing and existing.result in ("FAILED", "SKIPPED") and not force_execute:
            results.append({"detection_id": det_id, "target_email": target, "result": existing.result, "deduped": True, "message": "Already recorded."})
            continue
        details = run_containment(db, target, det_id, mode=mode)
        result = result_from_details(details)
        msg = _containment_message(details, result)
        logger.info("Disable account: %s -> %s | %s", target, result, msg)
        if existing:
            existing.result = result
            existing.details_json = details
            existing.time_bucket_start = time_bucket_start
        else:
            act = Action(
                detection_id=det_id,
                target_email=target,
                action_type="DISABLE_ACCOUNT",
                mode=mode,
                result=result,
                details_json=details,
                time_bucket_start=time_bucket_start,
            )
            db.add(act)
        if mode == "TAKEN" and result == "SUCCESS":
            det.status = "CONTAINED"
        elif det.status == "NEW":
            det.status = "TRIAGE"
        det.updated_at = datetime.now(timezone.utc)
        results.append({"detection_id": det_id, "target_email": target, "result": result, "message": msg})
    db.commit()
    return {"actions": results, "mode": mode}


async def disable_account_by_email(
    db: Session,
    user_email: str,
    reason: str = "",
    *,
    force_execute: bool = False,
) -> dict[str, Any]:
    """
    Run containment for a user by email (e.g. from Mailbox Filters when there is no alert).
    When force_execute=True (responder clicked Disable in UI), always run containment (TAKEN).
    Otherwise ACTION_FLAG controls mode. Rate limit, cooldown, protected list still apply.
    """
    settings = get_settings()
    mode = "TAKEN" if (force_execute or settings.action_flag) else "PROPOSED"
    target_email = (user_email or "").strip().lower()
    if not target_email or "@" not in target_email:
        raise HTTPException(status_code=400, detail="Invalid user_email")

    if mode == "TAKEN":
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.suspension_rate_limit_minutes)
        recent_successes = (
            db.query(Action)
            .filter(Action.action_type == "DISABLE_ACCOUNT")
            .filter(Action.result == "SUCCESS")
            .filter(Action.created_at >= cutoff)
            .count()
        )
        if recent_successes >= settings.suspension_rate_limit_max:
            log_audit(
                db,
                actor="system",
                action="SUSPENSION_RATE_LIMIT_TRIPPED",
                result="fail",
                error="circuit_breaker",
                payload_summary={"recent_successes": recent_successes, "limit": settings.suspension_rate_limit_max},
            )
            raise HTTPException(
                status_code=503,
                detail="Suspension rate limit exceeded; circuit breaker tripped.",
            )

    cooldown_cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.action_cooldown_minutes)
    recent = (
        db.query(Action)
        .filter(Action.target_email == target_email)
        .filter(Action.action_type == "DISABLE_ACCOUNT")
        .filter(Action.created_at >= cooldown_cutoff)
        .first()
    )
    if recent:
        return {
            "actions": [{"target_email": target_email, "result": "FAILED", "error": "cooldown_active", "message": "Cooldown active; wait before retrying."}],
            "mode": mode,
        }

    details = run_containment(db, target_email, detection_id=None, mode=mode)
    result = result_from_details(details)
    msg = _containment_message(details, result)
    logger.info("Disable account by email: %s -> %s | %s", target_email, result, msg)
    time_bucket_start = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    act = Action(
        detection_id=None,
        target_email=target_email,
        action_type="DISABLE_ACCOUNT",
        mode=mode,
        result=result,
        details_json=details,
        time_bucket_start=time_bucket_start,
    )
    db.add(act)
    db.commit()
    return {"actions": [{"target_email": target_email, "result": result, "message": msg}], "mode": mode}


def build_detection_email(
    detection: Detection,
    action_taken: bool,
    proposed_or_failed: str,
    ui_base_url: str,
) -> tuple[str, str]:
    """Subject and body (text) for detection notification email."""
    risk = detection.risk_level or "MEDIUM"
    subject = f"[{risk}] WASP Alert: {detection.target_email} (Score {detection.score})"
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
    if detection.status not in {"NEW", "TRIAGE"}:
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
    if detection_id is not None:
        existing = (
            db.query(Action)
            .filter(Action.detection_id == detection_id, Action.action_type == "EMAIL_NOTIFY")
            .first()
        )
        if existing:
            existing.result = "FAILED"
            existing.details_json = {"error": error}
            db.commit()
            return
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
        existing = (
            db.query(Action)
            .filter(Action.detection_id == detection_id, Action.action_type == "EMAIL_NOTIFY")
            .first()
        )
        if existing:
            existing.result = "SUCCESS"
            existing.details_json = {"subject": subject}
        else:
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
