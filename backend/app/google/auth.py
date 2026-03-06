"""Google API authentication with domain-wide delegation."""
from __future__ import annotations

import json
from typing import Any

from google.oauth2 import service_account
from google.auth.transport.requests import Request

from app.config import get_settings

SCOPES_REPORTS = [
    "https://www.googleapis.com/auth/admin.reports.audit.readonly",
]
SCOPES_DIRECTORY = [
    "https://www.googleapis.com/auth/admin.directory.user",
    "https://www.googleapis.com/auth/admin.directory.user.security",
]
# Narrow scope for Gmail filter inspection only (users.settings.filters.list)
SCOPES_GMAIL_FILTERS = [
    "https://www.googleapis.com/auth/gmail.settings.basic",
]


def get_credentials(scopes: list[str] | None = None) -> service_account.Credentials:
    settings = get_settings()
    creds_dict = settings.get_google_credentials()
    if not creds_dict or creds_dict == {}:
        raise ValueError("GOOGLE_CREDENTIALS_JSON not set or invalid")
    credentials = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=scopes or (SCOPES_REPORTS + SCOPES_DIRECTORY),
    )
    admin = settings.google_workspace_admin_user
    if admin:
        return credentials.with_subject(admin)
    return credentials
