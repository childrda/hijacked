"""Mailbox filters table for Gmail filter inspection.

Revision ID: 003
Revises: 002
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mailbox_filters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_email", sa.String(255), nullable=False),
        sa.Column("gmail_filter_id", sa.String(128), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("criteria_json", sa.JSON(), nullable=True),
        sa.Column("action_json", sa.JSON(), nullable=True),
        sa.Column("is_risky", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("risk_reasons_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.String(128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mailbox_filters_user_email"), "mailbox_filters", ["user_email"], unique=False)
    op.create_index(op.f("ix_mailbox_filters_gmail_filter_id"), "mailbox_filters", ["gmail_filter_id"], unique=False)
    op.create_index(op.f("ix_mailbox_filters_fingerprint"), "mailbox_filters", ["fingerprint"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mailbox_filters_fingerprint"), table_name="mailbox_filters")
    op.drop_index(op.f("ix_mailbox_filters_gmail_filter_id"), table_name="mailbox_filters")
    op.drop_index(op.f("ix_mailbox_filters_user_email"), table_name="mailbox_filters")
    op.drop_table("mailbox_filters")
