"""Admin SDK Reports API client for audit events."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generator

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.google.auth import get_credentials, SCOPES_REPORTS


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def fetch_audit_events(
    application_name: str,
    start_time: datetime,
    end_time: datetime | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Fetch audit events for the given application and time range."""
    creds = get_credentials(SCOPES_REPORTS)
    service = build("admin", "reports_v1", credentials=creds, cache_discovery=False)
    end = end_time or datetime.now(timezone.utc)
    request = service.activities().list(
        userKey="all",
        applicationName=application_name,
        startTime=start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        endTime=end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        maxResults=1000,
    )
    while request is not None:
        try:
            response = request.execute()
        except HttpError as e:
            raise RuntimeError(f"Reports API error: {e}") from e
        activities = response.get("items") or []
        for item in activities:
            yield item
        request = service.activities().list_next(request, response)
        if not request:
            break


def fetch_login_events(start_time: datetime, end_time: datetime | None = None) -> Generator[dict[str, Any], None, None]:
    """Fetch login audit events (login, token grant, etc.)."""
    yield from fetch_audit_events("login", start_time, end_time)


def fetch_admin_events(start_time: datetime, end_time: datetime | None = None) -> Generator[dict[str, Any], None, None]:
    """Fetch admin (directory/user) audit events."""
    yield from fetch_audit_events("admin", start_time, end_time)


def fetch_gmail_events(start_time: datetime, end_time: datetime | None = None) -> Generator[dict[str, Any], None, None]:
    """Fetch Gmail/calendar/drive audit events (mail rules, filters, etc.)."""
    for app in ("gmail", "calendar", "drive"):
        try:
            yield from fetch_audit_events(app, start_time, end_time)
        except HttpError:
            # Some apps may not be enabled
            continue
