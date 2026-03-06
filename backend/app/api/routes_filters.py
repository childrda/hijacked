"""Mailbox filter inspection: list, detail, approve, ignore, block, rescan."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.auth import get_current_user, require_responder
from app.db.session import get_db
from app.db.models import MailboxFilter, FilterScanLog
from app.services.audit_service import log_audit
from app.mailbox_filters.sync import _run_filter_scan_user

router = APIRouter(prefix="/api/filters", tags=["filters"])


class FilterApproveBody(BaseModel):
    pass


class FilterIgnoreBody(BaseModel):
    pass


class FilterBlockBody(BaseModel):
    pass


class RescanBody(BaseModel):
    user_email: str


def _filter_to_item(mf: MailboxFilter) -> dict:
    return {
        "id": mf.id,
        "user_email": mf.user_email,
        "gmail_filter_id": mf.gmail_filter_id,
        "fingerprint": mf.fingerprint,
        "criteria_json": mf.criteria_json,
        "action_json": mf.action_json,
        "is_risky": mf.is_risky,
        "risk_reasons_json": mf.risk_reasons_json,
        "status": mf.status,
        "first_seen_at": mf.first_seen_at.isoformat() if mf.first_seen_at else None,
        "last_seen_at": mf.last_seen_at.isoformat() if mf.last_seen_at else None,
        "approved_by": mf.approved_by,
        "approved_at": mf.approved_at.isoformat() if mf.approved_at else None,
        "removed_at": mf.removed_at.isoformat() if mf.removed_at else None,
        "created_at": mf.created_at.isoformat() if mf.created_at else None,
        "updated_at": mf.updated_at.isoformat() if mf.updated_at else None,
    }


@router.get("/scan-log")
def list_filter_scan_log(
    user_email: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """List recent Gmail filter scan runs (separate from filter state)."""
    q = db.query(FilterScanLog).order_by(FilterScanLog.scanned_at.desc()).limit(limit)
    if user_email:
        q = q.filter(FilterScanLog.user_email.ilike(f"%{user_email}%"))
    rows = q.all()
    return [
        {
            "id": r.id,
            "user_email": r.user_email,
            "scanned_at": r.scanned_at.isoformat() if r.scanned_at else None,
            "filters_count": r.filters_count,
            "success": r.success,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("")
def list_filters(
    user_email: str | None = Query(None),
    status: str | None = Query(None),
    risky_only: bool = Query(False),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    q = db.query(MailboxFilter).filter(MailboxFilter.removed_at.is_(None))
    if user_email:
        q = q.filter(MailboxFilter.user_email == user_email)
    if status:
        q = q.filter(MailboxFilter.status == status)
    if risky_only:
        q = q.filter(MailboxFilter.is_risky.is_(True))
    rows = q.order_by(MailboxFilter.last_seen_at.desc()).all()
    return [_filter_to_item(r) for r in rows]


@router.get("/{filter_id}")
def get_filter(
    filter_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    mf = db.get(MailboxFilter, filter_id)
    if not mf:
        raise HTTPException(status_code=404, detail="Filter not found")
    return _filter_to_item(mf)


@router.post("/{filter_id}/approve")
def approve_filter(
    filter_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_responder),
):
    mf = db.get(MailboxFilter, filter_id)
    if not mf:
        raise HTTPException(status_code=404, detail="Filter not found")
    now = datetime.now(timezone.utc)
    mf.status = "approved"
    mf.approved_by = current_user.get("username")
    mf.approved_at = now
    mf.updated_at = now
    db.commit()
    log_audit(
        db,
        actor=current_user.get("username", "unknown"),
        action="FILTER_APPROVE",
        result="success",
        target_user=mf.user_email,
        payload_summary={"filter_id": filter_id, "fingerprint": mf.fingerprint},
    )
    return _filter_to_item(mf)


@router.post("/{filter_id}/ignore")
def ignore_filter(
    filter_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_responder),
):
    mf = db.get(MailboxFilter, filter_id)
    if not mf:
        raise HTTPException(status_code=404, detail="Filter not found")
    mf.status = "ignored"
    mf.updated_at = datetime.now(timezone.utc)
    db.commit()
    log_audit(
        db,
        actor=current_user.get("username", "unknown"),
        action="FILTER_IGNORE",
        result="success",
        target_user=mf.user_email,
        payload_summary={"filter_id": filter_id, "fingerprint": mf.fingerprint},
    )
    return _filter_to_item(mf)


@router.post("/{filter_id}/block")
def block_filter(
    filter_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_responder),
):
    mf = db.get(MailboxFilter, filter_id)
    if not mf:
        raise HTTPException(status_code=404, detail="Filter not found")
    mf.status = "blocked"
    mf.updated_at = datetime.now(timezone.utc)
    db.commit()
    log_audit(
        db,
        actor=current_user.get("username", "unknown"),
        action="FILTER_BLOCK",
        result="success",
        target_user=mf.user_email,
        payload_summary={"filter_id": filter_id, "fingerprint": mf.fingerprint},
    )
    return _filter_to_item(mf)


@router.post("/rescan")
def rescan_user(
    body: RescanBody,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_responder),
):
    from app.config import get_settings
    settings = get_settings()
    if not settings.gmail_filter_inspection_enabled:
        raise HTTPException(status_code=503, detail="Gmail filter inspection is disabled")
    allowed = settings.filter_scan_user_scope_list
    if allowed and body.user_email.lower() not in [u.lower() for u in allowed]:
        raise HTTPException(status_code=403, detail="User not in scan scope")
    try:
        n_filters, n_alerts = _run_filter_scan_user(db, body.user_email)
    except Exception as e:
        log_audit(
            db,
            actor=current_user.get("username", "unknown"),
            action="FILTER_RESCAN",
            result="fail",
            target_user=body.user_email,
            error=str(e),
        )
        raise HTTPException(status_code=502, detail=str(e))
    log_audit(
        db,
        actor=current_user.get("username", "unknown"),
        action="FILTER_RESCAN",
        result="success",
        target_user=body.user_email,
        payload_summary={"filters_seen": n_filters, "new_alerts": n_alerts},
    )
    return {"ok": True, "filters_seen": n_filters, "new_alerts": n_alerts}
