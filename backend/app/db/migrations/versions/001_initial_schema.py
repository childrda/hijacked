"""Initial schema: users, raw_events, normalized_events, detections, actions, settings, admin_users.

Revision ID: 001
Revises:
Create Date: 2025-03-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("org_unit", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "raw_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("target_email", sa.String(255), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("geo", sa.String(255), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("hash_dedupe", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_raw_events_hash_dedupe"), "raw_events", ["hash_dedupe"], unique=True)
    op.create_index(op.f("ix_raw_events_target_email"), "raw_events", ["target_email"], unique=False)

    op.create_table(
        "normalized_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("raw_event_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["raw_event_id"], ["raw_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_normalized_events_event_type"), "normalized_events", ["event_type"], unique=False)

    op.create_table(
        "detections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("target_email", sa.String(255), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=True),
        sa.Column("rule_hits_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notification_count", sa.Integer(), nullable=True),
        sa.Column("last_notified_score", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_detections_target_email"), "detections", ["target_email"], unique=False)

    op.create_table(
        "actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("detection_id", sa.Integer(), nullable=True),
        sa.Column("target_email", sa.String(255), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["detection_id"], ["detections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_actions_target_email"), "actions", ["target_email"], unique=False)

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )

    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )


def downgrade() -> None:
    op.drop_table("admin_users")
    op.drop_table("settings")
    op.drop_index(op.f("ix_actions_target_email"), table_name="actions")
    op.drop_table("actions")
    op.drop_index(op.f("ix_detections_target_email"), table_name="detections")
    op.drop_table("detections")
    op.drop_index(op.f("ix_normalized_events_event_type"), table_name="normalized_events")
    op.drop_table("normalized_events")
    op.drop_index(op.f("ix_raw_events_target_email"), table_name="raw_events")
    op.drop_index(op.f("ix_raw_events_hash_dedupe"), table_name="raw_events")
    op.drop_table("raw_events")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
