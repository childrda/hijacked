"""Deterministic fingerprint for normalized Gmail filter content."""
from __future__ import annotations

import hashlib
import json

from app.mailbox_filters.normalize import normalized_filter_dict
from typing import Any


def filter_fingerprint(gmail_id: str, criteria: dict[str, Any] | None, action: dict[str, Any] | None) -> str:
    """Stable hash from normalized filter. Same logical filter => same fingerprint; change => new fingerprint."""
    payload = normalized_filter_dict(gmail_id, criteria, action)
    # JSON with sorted keys from _sort_keys; ensure no whitespace variance
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:64]
