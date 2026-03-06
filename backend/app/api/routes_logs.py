"""Admin logs: Google ingest (raw_events) and related views."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.db.models import RawEvent

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/ingest")
def list_ingest_logs(
    source: str | None = Query(None, description="Filter by source, e.g. gmail, login, admin"),
    target_email: str | None = Query(None, description="Filter by target email"),
    since: str | None = Query(None, description="ISO datetime, e.g. 2026-03-01T00:00:00Z"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    List raw events we pulled from Google (audit ingest). Lets admins see exactly what we ingested.
    """
    q = db.query(RawEvent).order_by(RawEvent.event_time.desc()).limit(limit)
    if source:
        q = q.filter(RawEvent.source == source)
    if target_email:
        q = q.filter(RawEvent.target_email.ilike(f"%{target_email}%"))
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            q = q.filter(RawEvent.event_time >= since_dt)
        except ValueError:
            pass
    rows = q.all()
    return [
        {
            "id": r.id,
            "source": r.source,
            "event_time": r.event_time.isoformat() if r.event_time else None,
            "actor_email": r.actor_email,
            "target_email": r.target_email,
            "ip": r.ip,
            "user_agent": r.user_agent,
            "geo": r.geo,
            "payload_json": r.payload_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
