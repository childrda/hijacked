"""Rule-based risky Gmail filter detection."""
from __future__ import annotations

from typing import Any

from app.config import get_settings

# Gmail system label IDs that imply risky actions when in removeLabelIds/addLabelIds
LABEL_TRASH = "TRASH"
LABEL_INBOX = "INBOX"
LABEL_UNREAD = "UNREAD"


def _text_matches_keywords(text: str | None, keywords: list[str]) -> bool:
    if not text or not keywords:
        return False
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def _criteria_targets_security(criteria: dict[str, Any] | None, keywords: list[str]) -> list[str]:
    """Check criteria for security-related patterns; return list of reasons."""
    reasons: list[str] = []
    if not criteria or not keywords:
        return reasons
    if _text_matches_keywords(criteria.get("from"), keywords):
        reasons.append("criteria_from_security_related")
    if _text_matches_keywords(criteria.get("to"), keywords):
        reasons.append("criteria_to_security_related")
    if _text_matches_keywords(criteria.get("subject"), keywords):
        reasons.append("criteria_subject_security_related")
    if _text_matches_keywords(criteria.get("query"), keywords):
        reasons.append("criteria_query_security_related")
    if _text_matches_keywords(criteria.get("negatedQuery"), keywords):
        reasons.append("criteria_negated_query_security_related")
    return reasons


def _action_risky(action: dict[str, Any] | None, domain: str, external_forwarding_only: bool) -> list[str]:
    """Check action for delete/archive/mark read/forward; return list of reasons."""
    reasons: list[str] = []
    if not action:
        return reasons
    add_ids = action.get("addLabelIds") or []
    remove_ids = action.get("removeLabelIds") or []
    forward = (action.get("forward") or "").strip().lower()

    if not external_forwarding_only:
        if LABEL_TRASH in add_ids:
            reasons.append("action_deletes_messages")
        if LABEL_UNREAD in remove_ids:
            reasons.append("action_marks_read")
        if LABEL_INBOX in remove_ids:
            reasons.append("action_archives")

    if forward:
        # Consider forward risky if external (not same domain)
        forward_domain = forward.split("@")[-1] if "@" in forward else ""
        if domain and forward_domain and forward_domain.lower() != domain.lower():
            reasons.append("action_forwards_externally")
        elif not domain:
            reasons.append("action_forwards")

    return reasons


def evaluate_risk(
    criteria: dict[str, Any] | None,
    action: dict[str, Any] | None,
    domain: str = "",
) -> tuple[bool, list[str]]:
    """
    Returns (is_risky, list of reason strings).
    Uses config: filter_risk_keywords_list, filter_external_forwarding_only.
    """
    settings = get_settings()
    keywords = settings.filter_risk_keywords_list
    external_only = settings.filter_external_forwarding_only
    reasons: list[str] = []

    reasons.extend(_criteria_targets_security(criteria, keywords))
    reasons.extend(_action_risky(action, domain, external_only))

    return bool(reasons), reasons
