"""Production hardening schema updates.

Revision ID: 002
Revises: 001
Create Date: 2026-03-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("detections", sa.Column("assigned_to", sa.String(length=128), nullable=True))
    op.add_column("detections", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("detections", sa.Column("rule_id", sa.String(length=128), nullable=True))
    op.add_column("detections", sa.Column("evidence_hash", sa.String(length=64), nullable=True))
    op.add_column("detections", sa.Column("time_bucket_start", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(
        "uq_detection_dedupe",
        "detections",
        ["target_email", "rule_id", "evidence_hash", "time_bucket_start"],
    )

    op.add_column("actions", sa.Column("time_bucket_start", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_action_detection_type", "actions", ["detection_id", "action_type"])
    op.create_unique_constraint(
        "uq_action_target_type_bucket",
        "actions",
        ["target_email", "action_type", "time_bucket_start"],
    )

    op.add_column("admin_users", sa.Column("role", sa.String(length=32), nullable=False, server_default="viewer"))

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_user", sa.String(length=255), nullable=True),
        sa.Column("alert_id", sa.Integer(), nullable=True),
        sa.Column("payload_summary", sa.JSON(), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"], unique=False)
    op.create_index("ix_audit_log_actor", "audit_log", ["actor"], unique=False)
    op.create_index("ix_audit_log_target_user", "audit_log", ["target_user"], unique=False)
    op.create_index("ix_audit_log_alert_id", "audit_log", ["alert_id"], unique=False)

    op.create_table(
        "poll_checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("last_seen_event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source"),
    )

    op.create_table(
        "poll_locks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner", sa.String(length=128), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("poll_locks")
    op.drop_table("poll_checkpoints")
    op.drop_index("ix_audit_log_alert_id", table_name="audit_log")
    op.drop_index("ix_audit_log_target_user", table_name="audit_log")
    op.drop_index("ix_audit_log_actor", table_name="audit_log")
    op.drop_index("ix_audit_log_timestamp", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_constraint("uq_action_target_type_bucket", "actions", type_="unique")
    op.drop_constraint("uq_action_detection_type", "actions", type_="unique")
    op.drop_column("actions", "time_bucket_start")

    op.drop_constraint("uq_detection_dedupe", "detections", type_="unique")
    op.drop_column("detections", "time_bucket_start")
    op.drop_column("detections", "evidence_hash")
    op.drop_column("detections", "rule_id")
    op.drop_column("detections", "notes")
    op.drop_column("detections", "assigned_to")

    op.drop_column("admin_users", "role")

