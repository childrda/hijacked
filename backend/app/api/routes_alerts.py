"""Alerts list, dismiss, bulk dismiss."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.services.alert_service import get_flagged, dismiss_alert, bulk_dismiss

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    status: str = Query("OPEN"),
    window: str = Query("24h"),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    _current_user: str = Depends(get_current_user),
):
    try:
        h = int(window.replace("h", "").replace("H", ""))
    except (ValueError, AttributeError):
        h = 24
    return get_flagged(db, status=status, window_hours=h, search=search)


@router.post("/{detection_id}/dismiss")
def dismiss(
    detection_id: int,
    db: Session = Depends(get_db),
    _current_user: str = Depends(get_current_user),
):
    ok = dismiss_alert(db, detection_id)
    return {"ok": ok}


@router.post("/bulk-dismiss")
def bulk_dismiss_route(
    body: dict,
    db: Session = Depends(get_db),
    _current_user: str = Depends(get_current_user),
):
    ids = body.get("alert_ids") or body.get("detection_ids") or []
    count = bulk_dismiss(db, ids)
    return {"dismissed": count}
