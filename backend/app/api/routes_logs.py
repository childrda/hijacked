"""Admin logs: Google ingest (raw_events) and related views."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.db.models import RawEvent

router = APIRouter(prefix="/api/logs", tags=["logs"])


def _geo_from_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Extract ip_address, region_code, subdivision_code, ip_asn from payload_json when present."""
    out: dict[str, Any] = {
        "ip_address": None,
        "region_code": None,
        "subdivision_code": None,
        "ip_asn": None,
    }
    if not payload:
        return out
    out["ip_address"] = payload.get("ipAddress")
    ni = payload.get("networkInfo")
    if isinstance(ni, dict):
        out["region_code"] = ni.get("regionCode")
        out["subdivision_code"] = ni.get("subdivisionCode")
        asn = ni.get("ipAsn")
        if isinstance(asn, list) and len(asn) > 0:
            out["ip_asn"] = asn[0]
        elif asn is not None:
            out["ip_asn"] = asn
    return out


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
    out = []
    for r in rows:
        from_payload = _geo_from_payload(r.payload_json)
        ip_display = r.ip or from_payload.get("ip_address")
        out.append({
            "id": r.id,
            "source": r.source,
            "event_time": r.event_time.isoformat() if r.event_time else None,
            "actor_email": r.actor_email,
            "target_email": r.target_email,
            "ip": ip_display or r.ip,
            "user_agent": r.user_agent,
            "geo": r.geo,
            "ip_address": ip_display,
            "region_code": from_payload.get("region_code"),
            "subdivision_code": from_payload.get("subdivision_code"),
            "ip_asn": from_payload.get("ip_asn"),
            "payload_json": r.payload_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out
