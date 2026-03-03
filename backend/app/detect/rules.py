"""Detection rules: event type -> base score and labels."""
from __future__ import annotations

# Rule name -> (base_score, short_label for UI)
RULES: dict[str, tuple[int, str]] = {
    "external_forwarding_enabled": (80, "New Forwarding Rule (external)"),
    "filter_with_delete": (70, "Delete Rule Created (All inbox)"),
    "filter_mark_read_archive": (50, "Mark-as-read + Archive filter"),
    "delegation_added": (60, "Delegation Added"),
    "pop_imap_enabled": (40, "POP/IMAP enabled"),
    "suspicious_oauth_grant": (60, "Suspicious OAuth grant"),
    "send_as_alias": (55, "Send As Alias (different domain)"),
    "mass_outbound_single": (70, "Mass Outbound Email (Single Message)"),
    "mass_outbound_burst": (60, "Mass Outbound Email (Burst)"),
    "mass_send_tampering_correlation": (30, "Mass Send + Mailbox Tampering Correlation"),
}

# Correlation bonus when multiple signals in 60 min window
CORRELATION_BONUS = 25


def get_score(rule_name: str) -> int:
    return RULES.get(rule_name, (0, ""))[0]


def get_label(rule_name: str) -> str:
    return RULES.get(rule_name, (0, ""))[1]
