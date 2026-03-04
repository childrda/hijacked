"""Settings and test email."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_responder
from app.config import get_settings
from app.notifier import get_notifier
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.services.audit_service import log_audit

router = APIRouter(prefix="/api/settings", tags=["settings"])


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
        "[Workspace Security Agent] Test email",
        "This is a test email from the Workspace Security Agent.",
    )
    log_audit(
        db,
        actor=current_user["username"],
        action="SETTINGS_TEST_EMAIL",
        payload_summary={"to": settings.support_email},
        result="success",
    )
    return {"ok": True, "sent_to": settings.support_email}
