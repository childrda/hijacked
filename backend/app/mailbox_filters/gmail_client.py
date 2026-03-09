"""Gmail API client for listing user filters (narrow scope; separate from audit polling)."""
from __future__ import annotations

import logging
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings
from app.google.auth import SCOPES_GMAIL_FILTERS

logger = logging.getLogger(__name__)


def _credentials_for_user(user_email: str):
    user_email = (user_email or "").strip().lower()
    if not user_email or "@" not in user_email:
        raise ValueError("Gmail impersonation requires a valid user email")
    if user_email.startswith("group:") or user_email.startswith("ou:"):
        raise ValueError(
            "Cannot impersonate a group or OU; use FILTER_SCAN_USER_SCOPE with group: or ou: to expand to user emails"
        )
    settings = get_settings()
    creds_dict = settings.get_google_credentials()
    if not creds_dict or creds_dict == {}:
        raise ValueError("GOOGLE_CREDENTIALS_JSON not set or invalid")
    credentials = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=SCOPES_GMAIL_FILTERS,
    )
    return credentials.with_subject(user_email)


def list_filters_for_user(user_email: str) -> list[dict[str, Any]]:
    """
    Call Gmail API users.settings.filters.list for the given user.
    Returns list of filter dicts with id, criteria, action.
    Raises on auth/API errors; returns [] on non-auth errors (e.g. user not found) after logging.
    """
    try:
        creds = _credentials_for_user(user_email)
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        response = service.users().settings().filters().list(userId="me").execute()
        filters = response.get("filter", []) or []
        return filters
    except HttpError as e:
        logger.warning("Gmail filters list failed for %s: %s", user_email, e, exc_info=False)
        raise
    except Exception as e:
        logger.warning("Gmail filters list error for %s: %s", user_email, e, exc_info=False)
        raise
