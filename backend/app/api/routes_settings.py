"""Settings and test email."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import require_responder
from app.config import get_settings
from app.db.session import get_db
from app.notifier import get_notifier
from app.services.audit_service import log_audit

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/polling")
def get_polling_settings(
    current_user: dict = Depends(require_responder),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    payload = {
        "poll_enabled_effective": settings.poll_enabled_effective,
        "poll_mode": settings.poll_mode,
        "poll_interval_seconds": settings.poll_interval_seconds,
        "poll_jitter_seconds": settings.poll_jitter_seconds,
        "poll_lock_ttl_seconds": settings.poll_lock_ttl_seconds,
        "poll_max_runtime_seconds": settings.poll_max_runtime_seconds,
        "lookback_minutes": settings.lookback_minutes,
    }
    log_audit(
        db,
        actor=current_user["username"],
        action="SETTINGS_VIEW_POLLING",
        payload_summary=payload,
        result="success",
    )
    return payload


@router.post("/test-email")
async def test_email(
    current_user: dict = Depends(require_responder),
    db: Session = Depends(get_db),
):
    """Send a test message to SUPPORT_EMAIL."""
    settings = get_settings()
    notifier = get_notifier()
    await notifier.send(
        settings.support_email,
        "[WASP] Test email",
        "This is a test email from WASP (Workspace Account Security Patrol).",
    )
    log_audit(
        db,
        actor=current_user["username"],
        action="SETTINGS_TEST_EMAIL",
        payload_summary={"to": settings.support_email},
        result="success",
    )
    return {"ok": True, "sent_to": settings.support_email}
