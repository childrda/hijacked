"""Sync Gmail filters into DB: normalize, fingerprint, risk, upsert, alert when appropriate."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import MailboxFilter, FilterScanLog, Detection
from app.mailbox_filters.gmail_client import list_filters_for_user
from app.mailbox_filters.normalize import normalize_criteria, normalize_action
from app.mailbox_filters.fingerprint import filter_fingerprint
from app.mailbox_filters.risk import evaluate_risk

logger = logging.getLogger(__name__)


def _run_filter_scan_user(db: Session, user_email: str) -> tuple[int, int]:
    """
    Fetch filters for user, upsert by fingerprint, mark missing as removed, evaluate risk.
    Returns (count_upserted, count_new_risky_alerts).
    """
    settings = get_settings()
    domain = (settings.domain or "").strip().lower()
    now = datetime.now(timezone.utc)
    try:
        raw_filters = list_filters_for_user(user_email)
    except Exception as e:
        logger.warning("Filter list failed for %s: %s", user_email, e)
        db.add(FilterScanLog(
            user_email=user_email,
            scanned_at=now,
            filters_count=0,
            success=False,
            error_message=str(e),
        ))
        db.commit()
        return 0, 0

    seen_fingerprints: set[str] = set()
    new_risky_alerts = 0

    for raw in raw_filters:
        gmail_id = str(raw.get("id", ""))
        criteria_raw = raw.get("criteria") or {}
        action_raw = raw.get("action") or {}
        criteria = normalize_criteria(criteria_raw)
        action = normalize_action(action_raw)
        fp = filter_fingerprint(gmail_id, criteria_raw, action_raw)
        seen_fingerprints.add(fp)
        is_risky, risk_reasons = evaluate_risk(criteria, action, domain)

        existing = (
            db.query(MailboxFilter)
            .filter(
                MailboxFilter.user_email == user_email,
                MailboxFilter.fingerprint == fp,
            )
            .first()
        )
        if existing:
            existing.last_seen_at = now
            existing.criteria_json = criteria
            existing.action_json = action
            existing.is_risky = is_risky
            existing.risk_reasons_json = risk_reasons
            existing.gmail_filter_id = gmail_id
            existing.updated_at = now
            if existing.removed_at:
                existing.removed_at = None
                existing.status = "new" if existing.status == "removed" else existing.status
            # Do not overwrite approved_by / approved_at
            # Alert: same fingerprint re-evaluated as risky after being approved (e.g. rule change) => re-alert
            if is_risky and existing.status == "approved":
                _create_filter_detection(db, existing, now)
                new_risky_alerts += 1
            elif is_risky and existing.status in ("new", "blocked") and not _detection_exists(db, existing):
                _create_filter_detection(db, existing, now)
                new_risky_alerts += 1
        else:
            # New filter
            row = MailboxFilter(
                user_email=user_email,
                gmail_filter_id=gmail_id,
                fingerprint=fp,
                criteria_json=criteria,
                action_json=action,
                is_risky=is_risky,
                risk_reasons_json=risk_reasons,
                status="new",
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(row)
            db.flush()
            if is_risky:
                _create_filter_detection(db, row, now)
                new_risky_alerts += 1

    # Mark filters no longer seen as removed
    missing = (
        db.query(MailboxFilter)
        .filter(
            MailboxFilter.user_email == user_email,
            MailboxFilter.removed_at.is_(None),
            ~MailboxFilter.fingerprint.in_(seen_fingerprints),
        )
        .all()
    )
    for row in missing:
        row.removed_at = now
        row.status = "removed"
        row.updated_at = now

    db.add(FilterScanLog(
        user_email=user_email,
        scanned_at=now,
        filters_count=len(raw_filters),
        success=True,
    ))
    db.commit()
    return len(raw_filters), new_risky_alerts


def _detection_exists(db: Session, mf: MailboxFilter) -> bool:
    """True if we already have a detection for this filter (rule_id + evidence_hash)."""
    return (
        db.query(Detection.id)
        .filter(
            Detection.target_email == mf.user_email,
            Detection.rule_id == "gmail_risky_filter",
            Detection.evidence_hash == mf.fingerprint,
        )
        .limit(1)
        .first()
        is not None
    )


def _create_filter_detection(db: Session, mf: MailboxFilter, now: datetime) -> None:
    """Create a detection record for a risky filter so it appears in alerts."""
    if _detection_exists(db, mf):
        return
    score = 80 if mf.is_risky else 50
    risk_level = "HIGH" if "forward" in (mf.risk_reasons_json or []) else "MEDIUM"
    detection = Detection(
        target_email=mf.user_email,
        window_start=now,
        window_end=now,
        score=score,
        risk_level=risk_level,
        reasons_json=["Gmail filter: " + ", ".join(mf.risk_reasons_json or [])],
        rule_hits_json=[{"rule": "gmail_risky_filter", "parameters": {"fingerprint": mf.fingerprint, "reasons": mf.risk_reasons_json or []}}],
        status="NEW",
        rule_id="gmail_risky_filter",
        evidence_hash=mf.fingerprint,
        time_bucket_start=now.replace(second=0, microsecond=0),
    )
    db.add(detection)


def run_filter_scan(db: Session) -> tuple[int, int]:
    """
    Run filter scan for all users in FILTER_SCAN_USER_SCOPE (or empty to skip).
    Scope can be: group:group@domain.com, ou:orgUnitId, ou:/path, or comma-separated emails.
    Returns (total_filters_seen, total_new_risky_alerts).
    """
    from app.google.scope_resolver import resolve_filter_scan_scope

    settings = get_settings()
    if not settings.gmail_filter_inspection_enabled or not settings.filter_scan_enabled:
        logger.info("Filter scan skipped: inspection or scan disabled")
        return 0, 0
    users = resolve_filter_scan_scope(settings.filter_scan_user_scope)
    if not users:
        logger.warning("Filter scan skipped: scope resolved to no users (check FILTER_SCAN_USER_SCOPE and group/OU access)")
        return 0, 0
    logger.info("Filter scan starting for %d user(s) from scope", len(users))
    total_filters = 0
    total_alerts = 0
    for user_email in users:
        try:
            n_filters, n_alerts = _run_filter_scan_user(db, user_email)
            total_filters += n_filters
            total_alerts += n_alerts
        except Exception as e:
            logger.warning("Filter scan failed for %s: %s", user_email, e, exc_info=True)
    return total_filters, total_alerts
