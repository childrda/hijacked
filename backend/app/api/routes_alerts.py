"""Alerts list, dismiss, bulk dismiss."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, require_responder
from app.db.session import get_db
from app.services.alert_service import (
    get_flagged,
    dismiss_alert,
    bulk_dismiss,
    get_alert_detail,
    update_status,
    assign_alert,
    set_notes,
)
from app.services.audit_service import log_audit

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    status: str = Query("NEW"),
    window: str = Query("24h"),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
):
    try:
        h = int(window.replace("h", "").replace("H", ""))
    except (ValueError, AttributeError):
        h = 24
    if status == "OPEN":
        rows = get_flagged(db, status="NEW", window_hours=h, search=search)
        rows += get_flagged(db, status="TRIAGE", window_hours=h, search=search)
        rows.sort(key=lambda x: x.get("detection_time") or "", reverse=True)
        return rows
    return get_flagged(db, status=status, window_hours=h, search=search)


@router.post("/{detection_id}/dismiss")
def dismiss(
    detection_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ok = dismiss_alert(db, detection_id)
    log_audit(
        db,
        actor=current_user["username"],
        action="ALERT_DISMISS",
        alert_id=detection_id,
        result="success" if ok else "fail",
    )
    return {"ok": ok}


@router.post("/bulk-dismiss")
def bulk_dismiss_route(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ids = body.get("alert_ids") or body.get("detection_ids") or []
    count = bulk_dismiss(db, ids)
    log_audit(
        db,
        actor=current_user["username"],
        action="ALERT_BULK_DISMISS",
        payload_summary={"ids": ids, "count": count},
    )
    return {"dismissed": count}


@router.get("/{detection_id}")
def get_alert(
    detection_id: int,
    db: Session = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
):
    detail = get_alert_detail(db, detection_id)
    if not detail:
        return {"ok": False}
    return detail


@router.post("/{detection_id}/status")
def set_alert_status(
    detection_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_responder),
):
    status = str(body.get("status") or "")
    allowed = {"NEW", "TRIAGE", "CONTAINED", "FALSE_POSITIVE", "CLOSED"}
    if status not in allowed:
        return {"ok": False, "error": "invalid_status"}
    ok = update_status(db, detection_id, status)
    log_audit(
        db,
        actor=current_user["username"],
        action="ALERT_STATUS_UPDATE",
        alert_id=detection_id,
        payload_summary={"status": status},
        result="success" if ok else "fail",
    )
    return {"ok": ok}


@router.post("/{detection_id}/assign")
def assign(
    detection_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_responder),
):
    assigned_to = body.get("assigned_to")
    ok = assign_alert(db, detection_id, assigned_to)
    log_audit(
        db,
        actor=current_user["username"],
        action="ALERT_ASSIGN",
        alert_id=detection_id,
        payload_summary={"assigned_to": assigned_to},
        result="success" if ok else "fail",
    )
    return {"ok": ok}


@router.post("/{detection_id}/notes")
def notes(
    detection_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    content = body.get("notes")
    ok = set_notes(db, detection_id, content)
    log_audit(
        db,
        actor=current_user["username"],
        action="ALERT_NOTES",
        alert_id=detection_id,
        payload_summary={"notes_len": len(content or "")},
        result="success" if ok else "fail",
    )
    return {"ok": ok}
