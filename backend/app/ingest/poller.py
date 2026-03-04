"""Poll Google Workspace audit events, persist raw + normalized, run detection."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import RawEvent, NormalizedEvent, Detection, Setting, PollCheckpoint
from app.detect.mass_send import MassSendConfig, generate_mass_send_hits
from app.detect.scoring import score_from_rule_hits, score_to_risk_level
from app.google.reports_client import fetch_gmail_events, fetch_login_events, fetch_admin_events
from app.ingest.normalizer import (
    normalize_activity,
    raw_event_payload,
    hash_dedupe,
)

CHECKPOINT_SOURCE = "google_reports"


def _get_checkpoint(db: Session) -> datetime:
    row = db.execute(select(PollCheckpoint).where(PollCheckpoint.source == CHECKPOINT_SOURCE)).scalars().first()
    if row and row.last_seen_event_time:
        return row.last_seen_event_time
    legacy = db.execute(select(Setting).where(Setting.key == "last_poll_checkpoint")).scalars().first()
    if legacy and legacy.value:
        try:
            return datetime.fromisoformat(legacy.value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    lookback = get_settings().lookback_minutes
    return (datetime.now(timezone.utc) - timedelta(minutes=lookback)).replace(microsecond=0)


def _set_checkpoint(db: Session, when: datetime) -> None:
    row = db.execute(select(PollCheckpoint).where(PollCheckpoint.source == CHECKPOINT_SOURCE)).scalars().first()
    if row:
        row.last_seen_event_time = when
    else:
        db.add(PollCheckpoint(source=CHECKPOINT_SOURCE, last_seen_event_time=when))
    db.commit()


def _ingest_source(db: Session, source: str, activities: list[dict]) -> list[tuple[RawEvent, list[NormalizedEvent]]]:
    """Store raw events and normalized events; return (raw, norm_list) for detection."""
    inserted: list[tuple[RawEvent, list[NormalizedEvent]]] = []
    for act in activities:
        h = hash_dedupe(source, act)
        existing = db.execute(select(RawEvent).where(RawEvent.hash_dedupe == h)).scalar_one_or_none()
        if existing:
            continue
        payload = raw_event_payload(act)
        event_time = payload.get("event_time") or datetime.now(timezone.utc)
        raw = RawEvent(
            source=source,
            event_time=event_time,
            actor_email=payload.get("actor_email"),
            target_email=payload.get("target_email"),
            ip=payload.get("ip"),
            user_agent=payload.get("user_agent"),
            geo=payload.get("geo"),
            payload_json=act,
            hash_dedupe=h,
        )
        db.add(raw)
        db.flush()
        norm_list = []
        for event_type, params in normalize_activity(source, act):
            norm = NormalizedEvent(raw_event_id=raw.id, event_type=event_type, parameters_json=params)
            db.add(norm)
            norm_list.append(norm)
        db.flush()
        inserted.append((raw, norm_list))
    return inserted


def _bucket_start(dt: datetime, minutes: int) -> datetime:
    mins = max(1, minutes)
    floor = (dt.minute // mins) * mins
    return dt.replace(minute=floor, second=0, microsecond=0)


def _evidence_hash(target_email: str, rule_hits: list[dict], bucket_start: datetime) -> str:
    core = {
        "target_email": target_email,
        "bucket_start": bucket_start.isoformat(),
        "rules": [
            {
                "rule": h.get("rule"),
                "params": h.get("parameters"),
            }
            for h in rule_hits
        ],
    }
    return hashlib.sha256(json.dumps(core, sort_keys=True, default=str).encode()).hexdigest()


def _run_detection(db: Session, window_minutes: int = 60) -> None:
    """Aggregate normalized events by target_email in time windows and create/update detections."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    settings = get_settings()
    mass_cfg = MassSendConfig.from_settings(settings)
    subq = (
        db.query(RawEvent.target_email, RawEvent.event_time, NormalizedEvent.event_type, NormalizedEvent.parameters_json)
        .join(NormalizedEvent, NormalizedEvent.raw_event_id == RawEvent.id)
        .filter(RawEvent.event_time >= cutoff)
        .filter(RawEvent.target_email.isnot(None))
        .filter(RawEvent.target_email != "")
    ).all()

    # Group by target_email
    from collections import defaultdict
    by_target: dict[str, list[dict]] = defaultdict(list)
    for target_email, event_time, event_type, params in subq:
        by_target[target_email].append({
            "event_time": event_time,
            "rule": event_type,
            "parameters": params or {},
        })

    for target_email, hits in by_target.items():
        if not hits:
            continue
        times = [h["event_time"] for h in hits]
        window_start = min(times)
        window_end = max(times)
        base_hits = [
            {"rule": h["rule"], "parameters": h["parameters"]}
            for h in hits
            if h["rule"] not in ("OUTBOUND_MESSAGE_SENT", "OUTBOUND_MESSAGE_SENT_MANY_RECIPIENTS")
        ]
        mass_hits = generate_mass_send_hits(target_email, hits, mass_cfg)
        rule_hits = base_hits + mass_hits
        score = score_from_rule_hits(rule_hits)
        if score <= 0:
            continue
        risk_level = score_to_risk_level(score)
        reasons = []
        for h in rule_hits:
            params = h.get("parameters") or {}
            reason = params.get("reason")
            if reason:
                reasons.append(str(reason))
            else:
                reasons.append(f"{h['rule']}: {params}")

        # Find or create detection for this target in this window (merge by target + overlapping window)
        bucket = _bucket_start(window_end, max(5, window_minutes))
        primary_rule = (rule_hits[0]["rule"] if rule_hits else "suspicious_activity")
        evidence_hash = _evidence_hash(target_email, rule_hits, bucket)
        existing = (
            db.query(Detection)
            .filter(Detection.target_email == target_email)
            .filter(Detection.rule_id == primary_rule)
            .filter(Detection.evidence_hash == evidence_hash)
            .filter(Detection.time_bucket_start == bucket)
            .first()
        )
        if existing:
            # Idempotent update
            all_hits = (existing.rule_hits_json or []) + rule_hits
            existing.window_start = min(existing.window_start, window_start)
            existing.window_end = max(existing.window_end, window_end)
            existing.score = score_from_rule_hits(all_hits)
            existing.risk_level = score_to_risk_level(existing.score)
            existing.reasons_json = (existing.reasons_json or []) + reasons
            existing.rule_hits_json = all_hits
            existing.updated_at = datetime.now(timezone.utc)
            existing.status = existing.status if existing.status in {"CONTAINED", "CLOSED", "FALSE_POSITIVE"} else "TRIAGE"
        else:
            det = Detection(
                target_email=target_email,
                window_start=window_start,
                window_end=window_end,
                score=score,
                risk_level=risk_level,
                reasons_json=reasons,
                rule_hits_json=rule_hits,
                status="NEW",
                rule_id=primary_rule,
                evidence_hash=evidence_hash,
                time_bucket_start=bucket,
            )
            db.add(det)
    db.commit()


def poll_once(db: Session) -> dict[str, Any]:
    """Run one poll cycle: fetch events, store, run detection, update checkpoint."""
    settings = get_settings()
    start = _get_checkpoint(db)
    end = datetime.now(timezone.utc)
    stats = {"raw_inserted": 0, "detections_updated": 0, "errors": []}

    try:
        gmail_list = list(fetch_gmail_events(start, end))
        stats["raw_inserted"] += len(_ingest_source(db, "gmail", gmail_list))
    except Exception as e:
        stats["errors"].append(f"gmail: {e}")

    try:
        login_list = list(fetch_login_events(start, end))
        stats["raw_inserted"] += len(_ingest_source(db, "login", login_list))
    except Exception as e:
        stats["errors"].append(f"login: {e}")

    try:
        admin_list = list(fetch_admin_events(start, end))
        stats["raw_inserted"] += len(_ingest_source(db, "admin", admin_list))
    except Exception as e:
        stats["errors"].append(f"admin: {e}")

    db.commit()
    _run_detection(db, window_minutes=settings.lookback_minutes * 4)
    _set_checkpoint(db, end)
    return stats
