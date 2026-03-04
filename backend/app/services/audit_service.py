"""Audit trail helpers."""
from __future__ import annotations

from typing import Any

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import AuditLog


def log_audit(
    db: Session,
    *,
    actor: str,
    action: str,
    target_user: str | None = None,
    alert_id: int | None = None,
    payload_summary: dict[str, Any] | None = None,
    result: str = "success",
    error: str | None = None,
) -> None:
    try:
        db.add(
            AuditLog(
                actor=actor,
                action=action,
                target_user=target_user,
                alert_id=alert_id,
                payload_summary=payload_summary or {},
                result=result,
                error=error,
            )
        )
        db.commit()
    except OperationalError:
        db.rollback()

