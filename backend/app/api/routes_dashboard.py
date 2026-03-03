"""Dashboard metrics API."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.db.models import Detection

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/metrics")
def get_metrics(
    window: str = Query("24h", description="e.g. 24h"),
    db: Session = Depends(get_db),
    _current_user: str = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        h = int(window.replace("h", "").replace("H", ""))
    except (ValueError, AttributeError):
        h = 24
    cutoff = datetime.now(timezone.utc) - timedelta(hours=h)

    open_detections = (
        db.query(Detection)
        .filter(Detection.window_end >= cutoff)
        .filter(Detection.status == "OPEN")
        .all()
    )
    critical = sum(1 for d in open_detections if (d.risk_level or "").upper() == "CRITICAL")
    high = sum(1 for d in open_detections if (d.risk_level or "").upper() == "HIGH")
    critical_alerts_count = critical + high
    recent_events_count = (
        db.query(func.count(Detection.id))
        .filter(Detection.window_end >= cutoff)
        .scalar()
    ) or 0

    # Trend: last 7 days daily counts
    trend_points: list[dict[str, Any]] = []
    for i in range(6, -1, -1):
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        c = (
            db.query(func.count(Detection.id))
            .filter(Detection.window_end >= day_start)
            .filter(Detection.window_end < day_end)
            .scalar()
        ) or 0
        trend_points.append({"date": day_start.date().isoformat(), "count": c})

    return {
        "critical_alerts_count": critical_alerts_count,
        "recent_events_count": recent_events_count,
        "trend_points": trend_points,
        "agent_status": "Online",
    }
