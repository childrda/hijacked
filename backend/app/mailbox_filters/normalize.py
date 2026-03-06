"""Normalize Gmail filter criteria and actions for stable fingerprinting."""
from __future__ import annotations

import json
from typing import Any


CRITERIA_KEYS = (
    "from",
    "to",
    "subject",
    "query",
    "negatedQuery",
    "hasAttachment",
    "excludeChats",
    "size",
    "sizeComparison",
)
ACTION_KEYS = ("addLabelIds", "removeLabelIds", "forward")


def _sort_keys(obj: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict with keys sorted for deterministic JSON."""
    return dict(sorted((k, v) for k, v in obj.items() if v is not None))


def normalize_criteria(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Canonical criteria: only known keys, sorted, normalized strings."""
    if not raw:
        return {}
    out: dict[str, Any] = {}
    for k in CRITERIA_KEYS:
        if k not in raw:
            continue
        v = raw[k]
        if v is None:
            continue
        if isinstance(v, str):
            out[k] = v.strip()
        elif isinstance(v, bool):
            out[k] = v
        elif isinstance(v, int):
            out[k] = v
        else:
            out[k] = v
    return _sort_keys(out)


def normalize_action(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Canonical action: only known keys, sorted lists, normalized forward address."""
    if not raw:
        return {}
    out: dict[str, Any] = {}
    if "addLabelIds" in raw and raw["addLabelIds"] is not None:
        out["addLabelIds"] = sorted(raw["addLabelIds"])
    if "removeLabelIds" in raw and raw["removeLabelIds"] is not None:
        out["removeLabelIds"] = sorted(raw["removeLabelIds"])
    if "forward" in raw and raw["forward"] is not None:
        out["forward"] = (raw["forward"] or "").strip().lower()
    return _sort_keys(out)


def normalized_filter_dict(gmail_id: str, criteria: dict[str, Any] | None, action: dict[str, Any] | None) -> dict[str, Any]:
    """Single dict suitable for hashing: id + normalized criteria + normalized action."""
    return _sort_keys({
        "id": gmail_id,
        "criteria": normalize_criteria(criteria),
        "action": normalize_action(action),
    })
