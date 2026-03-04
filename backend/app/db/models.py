"""SQLAlchemy models for workspace security agent."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    org_unit: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class RawEvent(Base):
    __tablename__ = "raw_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    geo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    hash_dedupe: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    normalized_events: Mapped[list[NormalizedEvent]] = relationship(
        "NormalizedEvent", back_populates="raw_event", cascade="all, delete-orphan"
    )


class NormalizedEvent(Base):
    __tablename__ = "normalized_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("raw_events.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    parameters_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    raw_event: Mapped[RawEvent] = relationship("RawEvent", back_populates="normalized_events")


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    reasons_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    rule_hits_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")  # NEW, TRIAGE, CONTAINED, FALSE_POSITIVE, CLOSED
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evidence_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    time_bucket_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notification_count: Mapped[int] = mapped_column(Integer, default=0)
    last_notified_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    actions: Mapped[list[Action]] = relationship(
        "Action", back_populates="detection", cascade="all, delete-orphan", order_by="Action.created_at"
    )

    __table_args__ = (
        UniqueConstraint(
            "target_email",
            "rule_id",
            "evidence_hash",
            "time_bucket_start",
            name="uq_detection_dedupe",
        ),
    )


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detection_id: Mapped[int | None] = mapped_column(ForeignKey("detections.id", ondelete="SET NULL"), nullable=True)
    target_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)  # DISABLE_ACCOUNT, EMAIL_NOTIFY, etc.
    mode: Mapped[str] = mapped_column(String(32), nullable=False)  # TAKEN, PROPOSED
    result: Mapped[str] = mapped_column(String(32), nullable=False)  # SUCCESS, FAILED, PARTIAL
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    time_bucket_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    detection: Mapped[Detection | None] = relationship("Detection", back_populates="actions")

    __table_args__ = (
        UniqueConstraint("detection_id", "action_type", name="uq_action_detection_type"),
        UniqueConstraint("target_email", "action_type", "time_bucket_start", name="uq_action_target_type_bucket"),
    )


class Setting(Base):
    """Key-value state (e.g. last poll checkpoint)."""
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class AdminUser(Base):
    """Local admin for UI auth (dev); pluggable JWT/SSO later."""
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")  # viewer | responder
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_user: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    alert_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    payload_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result: Mapped[str] = mapped_column(String(32), nullable=False)  # success | fail
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class PollCheckpoint(Base):
    __tablename__ = "poll_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    last_seen_event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class PollLock(Base):
    __tablename__ = "poll_locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
