"""Disable account (containment) action."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_responder
from app.db.session import get_db
from app.services.action_service import disable_account, disable_account_by_email, send_detection_notification
from app.services.audit_service import log_audit

router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.post("/disable-account")
async def post_disable_account(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_responder),
):
    alert_ids = body.get("alert_ids") or body.get("detection_ids") or []
    reason = body.get("reason") or ""
    # Responder clicked Disable in UI: always execute containment (ACTION_FLAG only gates automatic flows)
    result = await disable_account(db, alert_ids, reason=reason, force_execute=True)
    for action in result.get("actions") or []:
        det_id = action.get("detection_id")
        if det_id:
            await send_detection_notification(db, det_id, action_taken=result.get("mode") == "TAKEN")
    log_audit(
        db,
        actor=current_user["username"],
        action="DISABLE_ACCOUNT",
        payload_summary={"alert_ids": alert_ids, "reason": reason, "mode": result.get("mode")},
        result="success",
    )
    return result


class DisableByEmailBody(BaseModel):
    user_email: str
    reason: str = ""


@router.post("/disable-account-by-email")
async def post_disable_account_by_email(
    body: DisableByEmailBody,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_responder),
):
    """Run containment for a user by email (e.g. from Mailbox Filters when there is no alert)."""
    result = await disable_account_by_email(db, body.user_email.strip(), reason=body.reason, force_execute=True)
    log_audit(
        db,
        actor=current_user["username"],
        action="DISABLE_ACCOUNT_BY_EMAIL",
        payload_summary={"user_email": body.user_email, "reason": body.reason, "mode": result.get("mode")},
        result="success",
    )
    return result
