"""Normalize Admin SDK / Reports API activities into event types and parameters."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings

# Map API event names + params to our rule names and parameters
def _parse_event_time(activity: dict) -> datetime | None:
    for ev in activity.get("events") or []:
        for p in ev.get("parameters") or []:
            if p.get("name") == "event_time" and p.get("value"):
                try:
                    return datetime.fromisoformat(p["value"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
    return None


def _actor_email(activity: dict) -> str | None:
    actor = activity.get("actor") or {}
    return actor.get("email") or (actor.get("profileId") if isinstance(actor.get("profileId"), str) else None)


def _actor_caller_type(activity: dict) -> str | None:
    return (activity.get("actor") or {}).get("callerType")


def normalize_gmail_activity(activity: dict) -> list[tuple[str, dict]]:
    """Return list of (event_type, parameters_json) for a Gmail activity."""
    results = []
    events = activity.get("events") or []
    actor = _actor_email(activity)
    for ev in events:
        name = ev.get("name") or ""
        params = _params_to_dict(ev.get("parameters") or [])
        if "MAIL_RECORD_CREATED" in name or "mail_rule_created" in name.lower():
            # Forwarding / filter
            rule_type = (params.get("rule_type") or params.get("type") or "").lower()
            dest = params.get("forward_to") or params.get("destination") or params.get("email") or ""
            if "forward" in rule_type or dest:
                if dest and "@" in str(dest):
                    domain = str(dest).split("@")[-1]
                    if domain and "gmail.com" not in domain.lower() and "google.com" not in domain.lower():
                        results.append(("external_forwarding_enabled", {"destination": dest, **params}))
                    else:
                        results.append(("forwarding_enabled", {"destination": dest, **params}))
            if "filter" in rule_type or "delete" in str(params).lower():
                results.append(("filter_with_delete", params))
            if "archive" in str(params).lower() or "mark_read" in str(params).lower():
                results.append(("filter_mark_read_archive", params))
        if "DELEGATION" in name or "delegation" in name.lower():
            results.append(("delegation_added", {"delegate": params.get("delegate"), **params}))
        if "send_as" in name.lower() or "sendAs" in name:
            alias = params.get("send_as") or params.get("alias") or ""
            if alias and "@" in str(alias):
                results.append(("send_as_alias", {"alias": alias, **params}))
        # Outbound message send events (mass send phishing indicator source).
        lower_name = name.lower()
        if (
            "message_sent" in lower_name
            or "send_message" in lower_name
            or "mail_sent" in lower_name
            or lower_name == "send"
            or "smtp_send" in lower_name
        ):
            recipients = _extract_recipients(params)
            recipient_count = _extract_recipient_count(params, recipients)
            message_id = params.get("message_id") or params.get("rfc822_message_id")
            subject = params.get("subject") or params.get("mail_subject")
            outbound = {
                "sender": actor,
                "recipients": recipients,
                "recipient_count": recipient_count,
                "message_id": message_id,
                "subject": subject,
                "to": params.get("to"),
                "cc": params.get("cc"),
                "bcc": params.get("bcc"),
                "delivery_status": params.get("delivery_status") or params.get("status"),
            }
            results.append(("OUTBOUND_MESSAGE_SENT", outbound))
            if recipient_count >= get_settings().mass_send_recipient_threshold:
                results.append(("OUTBOUND_MESSAGE_SENT_MANY_RECIPIENTS", outbound))
    return results


def normalize_login_activity(activity: dict) -> list[tuple[str, dict]]:
    """Normalize login/token events."""
    results = []
    events = activity.get("events") or []
    for ev in events:
        name = (ev.get("name") or "").lower()
        params = _params_to_dict(ev.get("parameters") or [])
        if "oauth" in name or "token" in name or "authorization" in name:
            app = params.get("application_name") or params.get("client_id") or ""
            if app and "google" not in (app or "").lower():
                results.append(("suspicious_oauth_grant", {"application": app, **params}))
    return results


def normalize_admin_activity(activity: dict) -> list[tuple[str, dict]]:
    """Normalize admin/directory events (e.g. POP/IMAP)."""
    results = []
    events = activity.get("events") or []
    for ev in events:
        name = (ev.get("name") or "").lower()
        params = _params_to_dict(ev.get("parameters") or [])
        if "pop" in name or "imap" in name or "imap_enable" in name or "pop_enable" in name:
            results.append(("pop_imap_enabled", params))
    return results


def normalize_activity(source: str, activity: dict) -> list[tuple[str, dict]]:
    """Dispatch by source. Returns list of (event_type, parameters_json)."""
    if source == "gmail":
        return normalize_gmail_activity(activity)
    if source == "login":
        return normalize_login_activity(activity)
    if source == "admin":
        return normalize_admin_activity(activity)
    return []


def raw_event_payload(activity: dict) -> dict:
    """Extract common fields for raw_events from an activity."""
    events = activity.get("events") or []
    event_time = _parse_event_time(activity)
    actor = _actor_email(activity)
    ip = None
    user_agent = None
    for ev in events:
        for p in ev.get("parameters") or []:
            if p.get("name") == "ip_address":
                ip = p.get("value")
            if p.get("name") == "user_agent" or p.get("name") == "user_agent_string":
                user_agent = p.get("value")
    # target: often in events or actor for "impersonated" user
    target = actor  # default
    for ev in events:
        for p in ev.get("parameters") or []:
            if p.get("name") in ("user_email", "target_user", "email", "destination"):
                if p.get("value") and "@" in str(p.get("value")):
                    target = p.get("value")
                    break
    return {
        "event_time": event_time,
        "actor_email": actor,
        "target_email": target,
        "ip": ip,
        "user_agent": user_agent,
        "geo": None,
        "payload_json": activity,
    }


def hash_dedupe(source: str, activity: dict) -> str:
    """Stable hash for deduplication."""
    raw = json.dumps({"source": source, "id": activity.get("id"), "timestamp": activity.get("timestamp")}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _params_to_dict(parameters: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for p in parameters:
        name = p.get("name")
        if not name:
            continue
        if "value" in p:
            out[name] = p.get("value")
        elif "multiValue" in p:
            out[name] = p.get("multiValue")
        elif "boolValue" in p:
            out[name] = p.get("boolValue")
        elif "intValue" in p:
            out[name] = p.get("intValue")
    return out


def _extract_recipients(params: dict[str, Any]) -> list[str]:
    values = []
    for key in ("recipients", "recipient", "to", "cc", "bcc", "all_recipients", "recipient_list"):
        if key in params:
            values.append(params.get(key))
    recips: list[str] = []
    for v in values:
        if v is None:
            continue
        if isinstance(v, list):
            items = v
        else:
            items = str(v).replace(";", ",").split(",")
        for item in items:
            s = str(item).strip().lower()
            if "@" in s:
                recips.append(s)
    # de-dupe while preserving order
    seen = set()
    out = []
    for r in recips:
        if r in seen:
            continue
        seen.add(r)
        out.append(r)
    return out


def _extract_recipient_count(params: dict[str, Any], recipients: list[str]) -> int:
    for key in ("recipient_count", "recipients_count", "num_recipients", "total_recipients"):
        val = params.get(key)
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                continue
    return len(recipients)
