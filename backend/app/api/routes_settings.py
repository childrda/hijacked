"""Settings and test email."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.config import get_settings
from app.notifier import get_notifier

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.post("/test-email")
async def test_email(
    _current_user: str = Depends(get_current_user),
):
    """Send a test message to SUPPORT_EMAIL."""
    settings = get_settings()
    notifier = get_notifier()
    await notifier.send(
        settings.support_email,
        "[Workspace Security Agent] Test email",
        "This is a test email from the Workspace Security Agent.",
    )
    return {"ok": True, "sent_to": settings.support_email}
