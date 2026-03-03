"""Containment: optionally disable in AD and/or Google Workspace (both only when ACTION_FLAG is True)."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.google.directory_client import suspend_user, sign_out_user, revoke_all_tokens
from app.actions.ad_client import disable_user_in_ad, ad_disable_available


def _google_workspace_enabled() -> bool:
    return get_settings().enable_google_workspace


def run_containment(db: Session, target_email: str, detection_id: int | None, mode: str = "TAKEN") -> dict[str, Any]:
    """
    Run containment. Only runs when mode=TAKEN (i.e. ACTION_FLAG is True).
    Which backends run is controlled by config (no code changes needed):
    - enable_active_directory=True and AD_* set → disable user in AD first.
    - enable_google_workspace=True → suspend in Google, sign-out, revoke tokens.
    mode: TAKEN = do it; PROPOSED = record only, no changes.
    Returns combined details_json for actions table.
    """
    details: dict[str, Any] = {"ad_disable": None, "suspend": None, "sign_out": None, "revoke_tokens": None}
    if mode == "PROPOSED":
        details["proposed"] = True
        return details

    # 1. Active Directory (only if enabled and configured)
    if ad_disable_available():
        details["ad_disable"] = disable_user_in_ad(target_email)
    else:
        details["ad_disable"] = {"skipped": True, "reason": "Active Directory disabled or not configured"}

    # 2. Google Workspace (only if enabled)
    if _google_workspace_enabled():
        suspend_res = suspend_user(target_email)
        details["suspend"] = suspend_res
        details["sign_out"] = sign_out_user(target_email)
        details["revoke_tokens"] = revoke_all_tokens(target_email)
        if suspend_res.get("error"):
            details["suspend_error"] = suspend_res.get("error")
    else:
        details["suspend"] = details["sign_out"] = details["revoke_tokens"] = {
            "skipped": True,
            "reason": "Google Workspace disabled",
        }

    return details


def result_from_details(details: dict[str, Any]) -> str:
    if details.get("proposed"):
        return "SUCCESS"  # proposed counts as recorded
    err = details.get("suspend_error") or (details.get("suspend") or {}).get("error")
    ad = details.get("ad_disable") or {}
    if ad.get("error") and not ad.get("skipped"):
        err = err or ad.get("error")
    if err:
        return "FAILED"
    return "SUCCESS"
