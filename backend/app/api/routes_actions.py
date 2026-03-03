"""Disable account (containment) action."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.services.action_service import disable_account, send_detection_notification

router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.post("/disable-account")
async def post_disable_account(
    body: dict,
    db: Session = Depends(get_db),
    _current_user: str = Depends(get_current_user),
):
    alert_ids = body.get("alert_ids") or body.get("detection_ids") or []
    reason = body.get("reason") or ""
    result = await disable_account(db, alert_ids, reason=reason)
    for action in result.get("actions") or []:
        det_id = action.get("detection_id")
        if det_id:
            await send_detection_notification(db, det_id, action_taken=result.get("mode") == "TAKEN")
    return result
