"""
Resolve FILTER_SCAN_USER_SCOPE to a list of user emails.
Supports: group:group@domain.com (email group), ou:orgUnitId or ou:/path (user group/OU), or comma-separated emails.
"""
from __future__ import annotations

import logging
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings
from app.google.auth import get_credentials, SCOPES_DIRECTORY, SCOPES_GROUP_MEMBERS

logger = logging.getLogger(__name__)


def _list_group_member_emails(group_email: str) -> list[str]:
    """List member emails of a Google Group (email group). Returns USER-type members only."""
    group_email = (group_email or "").strip()
    if not group_email or "@" not in group_email:
        return []
    try:
        creds = get_credentials(SCOPES_GROUP_MEMBERS)
        service = build("admin", "directory_v1", credentials=creds, cache_discovery=False)
        emails: list[str] = []
        page_token: str | None = None
        while True:
            request = service.members().list(
                groupKey=group_email,
                maxResults=200,
                pageToken=page_token or None,
            )
            response = request.execute()
            for m in response.get("members") or []:
                if m.get("type") == "USER" and m.get("email"):
                    emails.append(m["email"].lower())
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        logger.info("Resolved group %s to %d user(s)", group_email, len(emails))
        return emails
    except HttpError as e:
        logger.warning("Failed to list group %s: %s", group_email, e)
        return []
    except Exception as e:
        logger.warning("Error resolving group %s: %s", group_email, e, exc_info=True)
        return []


def _list_org_unit_user_emails(ou_id_or_path: str) -> list[str]:
    """List primary emails of users in an organizational unit (user group)."""
    ou_id_or_path = (ou_id_or_path or "").strip()
    if not ou_id_or_path:
        return []
    try:
        creds = get_credentials(SCOPES_DIRECTORY)
        service = build("admin", "directory_v1", credentials=creds, cache_discovery=False)
        if ou_id_or_path.startswith("/"):
            query = f"orgUnitPath='{ou_id_or_path}'"
        else:
            query = f"orgUnitId={ou_id_or_path}"
        emails: list[str] = []
        page_token: str | None = None
        while True:
            request = service.users().list(
                customer="my_customer",
                query=query,
                maxResults=500,
                orderBy="email",
                pageToken=page_token or None,
            )
            response = request.execute()
            for u in response.get("users") or []:
                if u.get("primaryEmail"):
                    emails.append(u["primaryEmail"].lower())
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        logger.info("Resolved OU %s to %d user(s)", ou_id_or_path, len(emails))
        return emails
    except HttpError as e:
        logger.warning("Failed to list OU %s: %s", ou_id_or_path, e)
        return []
    except Exception as e:
        logger.warning("Error resolving OU %s: %s", ou_id_or_path, e, exc_info=True)
        return []


def resolve_filter_scan_scope(scope: str) -> list[str]:
    """
    Resolve FILTER_SCAN_USER_SCOPE to a list of user email addresses.

    - group:group@domain.com  → Google Group (email group): list members.
    - ou:orgUnitId or ou:/Path/To/OU  → Organizational unit (user group): list users in OU.
    - Else  → Comma-separated list of emails (unchanged).

    Returns empty list if scope is empty or resolution fails.
    """
    scope = (scope or "").strip()
    if not scope:
        return []

    lower = scope.lower()
    if lower.startswith("group:"):
        group_email = scope[6:].strip()
        return _list_group_member_emails(group_email)
    if lower.startswith("ou:"):
        ou_value = scope[3:].strip()
        return _list_org_unit_user_emails(ou_value)

    # Backward compat: comma-separated list of emails
    return [e.strip().lower() for e in scope.split(",") if e.strip()]
