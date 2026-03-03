"""Score aggregation and risk level from rule hits."""
from __future__ import annotations

from app.detect.rules import CORRELATION_BONUS, get_score


def score_from_rule_hits(rule_hits: list[dict]) -> int:
    """Sum base scores and add correlation bonus if multiple distinct rules in window."""
    total = 0
    seen = set()
    for hit in rule_hits:
        name = hit.get("rule") or hit.get("rule_name") or ""
        params = hit.get("parameters") or {}
        override = params.get("points_override")
        if override is not None:
            try:
                total += int(override)
            except (TypeError, ValueError):
                total += get_score(name)
        else:
            total += get_score(name)
        seen.add(name)
    if len(seen) >= 2:
        total += CORRELATION_BONUS
    return total


def score_to_risk_level(score: int) -> str:
    if score >= 100:
        return "CRITICAL"
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"
