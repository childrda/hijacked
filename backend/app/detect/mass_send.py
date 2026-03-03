"""Mass outbound email burst detection helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

TAMPERING_RULES = {
    "external_forwarding_enabled",
    "filter_with_delete",
    "filter_mark_read_archive",
    "delegation_added",
    "suspicious_oauth_grant",
    "send_as_alias",
}


@dataclass
class MassSendConfig:
    enabled: bool = True
    recipient_threshold: int = 50
    window_minutes: int = 10
    message_threshold: int = 20
    unique_recipient_threshold: int = 80
    internal_only_ignore: bool = True
    allowlist_senders: set[str] | None = None
    allowlist_subject_keywords: list[str] | None = None
    severity_points_single: int = 70
    severity_points_burst: int = 60
    domain: str = "yourdomain.tld"

    @classmethod
    def from_settings(cls, settings: Any) -> "MassSendConfig":
        senders = set(settings.mass_send_allowlist_senders_list)
        keywords = settings.mass_send_allowlist_subject_keywords_list
        return cls(
            enabled=settings.mass_send_enabled,
            recipient_threshold=settings.mass_send_recipient_threshold,
            window_minutes=settings.mass_send_window_minutes,
            message_threshold=settings.mass_send_message_threshold,
            unique_recipient_threshold=settings.mass_send_unique_recipient_threshold,
            internal_only_ignore=settings.mass_send_internal_only_ignore,
            allowlist_senders=senders,
            allowlist_subject_keywords=keywords,
            severity_points_single=settings.mass_send_severity_points_single,
            severity_points_burst=settings.mass_send_severity_points_burst,
            domain=settings.domain,
        )


def parse_recipients(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for v in value:
            out.extend(parse_recipients(v))
        return out
    s = str(value).replace(";", ",")
    parts = [p.strip().lower() for p in s.split(",") if p.strip()]
    return [p for p in parts if "@" in p]


def is_sender_allowlisted(sender: str | None, cfg: MassSendConfig) -> bool:
    if not sender:
        return False
    sender_l = sender.lower()
    return sender_l in (cfg.allowlist_senders or set())


def is_subject_allowlisted(subject: str | None, cfg: MassSendConfig) -> bool:
    if not subject:
        return False
    s = subject.lower()
    return any(k in s for k in (cfg.allowlist_subject_keywords or []))


def split_internal_external(recipients: list[str], domain: str) -> tuple[int, int]:
    d = domain.lower().strip()
    internal = 0
    external = 0
    for r in recipients:
        if r.endswith(f"@{d}"):
            internal += 1
        else:
            external += 1
    return internal, external


def _recipient_count(params: dict[str, Any], recipients: list[str]) -> int:
    for k in ("recipient_count", "recipients_count", "num_recipients", "total_recipients"):
        val = params.get(k)
        if val is not None and str(val).isdigit():
            return int(str(val))
    return len(recipients)


def _outbound_events(recent_hits: list[dict]) -> list[dict]:
    return [h for h in recent_hits if h.get("rule") == "OUTBOUND_MESSAGE_SENT"]


def _tampering_times(recent_hits: list[dict]) -> list[datetime]:
    out = []
    for h in recent_hits:
        if h.get("rule") in TAMPERING_RULES and isinstance(h.get("event_time"), datetime):
            out.append(h["event_time"])
    return out


def generate_mass_send_hits(sender: str, recent_hits: list[dict], cfg: MassSendConfig) -> list[dict]:
    if not cfg.enabled or is_sender_allowlisted(sender, cfg):
        return []

    outbound_events = _outbound_events(recent_hits)
    if not outbound_events:
        return []

    hits: list[dict] = []

    # Rule 1: single message fanout
    best_single = None
    for ev in outbound_events:
        params = dict(ev.get("parameters") or {})
        subject = params.get("subject")
        if is_subject_allowlisted(subject, cfg):
            continue
        recipients = parse_recipients(params.get("recipients"))
        recipient_count = _recipient_count(params, recipients)
        internal_count, external_count = split_internal_external(recipients, cfg.domain)
        if cfg.internal_only_ignore and recipient_count > 0 and external_count == 0:
            continue
        if recipient_count >= cfg.recipient_threshold:
            if best_single is None or recipient_count > best_single["recipient_count"]:
                best_single = {
                    "recipient_count": recipient_count,
                    "internal_count": internal_count,
                    "external_count": external_count,
                    "subject": subject,
                    "message_id": params.get("message_id"),
                    "event_time": ev.get("event_time"),
                }

    if best_single:
        reason = f"Single email sent to {best_single['recipient_count']} recipients"
        hits.append(
            {
                "rule": "mass_outbound_single",
                "parameters": {
                    **best_single,
                    "reason": reason,
                    "points_override": cfg.severity_points_single,
                },
            }
        )

    # Rule 2: rolling-window burst
    now = max(
        [e.get("event_time") for e in outbound_events if isinstance(e.get("event_time"), datetime)],
        default=datetime.now(timezone.utc),
    )
    cutoff = now - timedelta(minutes=cfg.window_minutes)
    burst_events = []
    for ev in outbound_events:
        t = ev.get("event_time")
        if not isinstance(t, datetime) or t < cutoff:
            continue
        params = dict(ev.get("parameters") or {})
        if is_subject_allowlisted(params.get("subject"), cfg):
            continue
        burst_events.append(ev)

    if burst_events:
        messages_sent = len(burst_events)
        recipient_set: set[str] = set()
        recipient_estimate = 0
        for ev in burst_events:
            params = dict(ev.get("parameters") or {})
            recipients = parse_recipients(params.get("recipients"))
            recipient_set.update(recipients)
            recipient_estimate += _recipient_count(params, recipients)
        unique_recipients = len(recipient_set) if recipient_set else recipient_estimate
        internal_u, external_u = split_internal_external(list(recipient_set), cfg.domain) if recipient_set else (0, 0)
        if cfg.internal_only_ignore and unique_recipients > 0 and external_u == 0 and recipient_set:
            pass
        else:
            if messages_sent >= cfg.message_threshold or unique_recipients >= cfg.unique_recipient_threshold:
                reason = (
                    f"Burst outbound mail: {messages_sent} messages / "
                    f"{unique_recipients} unique recipients in {cfg.window_minutes} minutes"
                )
                hits.append(
                    {
                        "rule": "mass_outbound_burst",
                        "parameters": {
                            "messages_sent": messages_sent,
                            "unique_recipients": unique_recipients,
                            "internal_external_breakdown": {
                                "internal_unique": internal_u,
                                "external_unique": external_u,
                            },
                            "window_minutes": cfg.window_minutes,
                            "reason": reason,
                            "points_override": cfg.severity_points_burst,
                        },
                    }
                )

    # Correlation bonus if mass send and mailbox tampering are near each other.
    if hits:
        tampering_times = _tampering_times(recent_hits)
        mass_times = []
        for h in hits:
            t = (h.get("parameters") or {}).get("event_time")
            if isinstance(t, datetime):
                mass_times.append(t)
        if tampering_times and mass_times:
            correlated = any(abs((mt - tt).total_seconds()) <= 3600 for mt in mass_times for tt in tampering_times)
            if correlated:
                hits.append(
                    {
                        "rule": "mass_send_tampering_correlation",
                        "parameters": {
                            "reason": "Mass send correlated with mailbox tampering",
                            "points_override": 30,
                        },
                    }
                )
    return hits

