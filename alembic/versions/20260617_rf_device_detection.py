"""add RF device-detection tables

Revision ID: 20260617_rf_detection
Revises: 20260616_evidence_retention
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260617_rf_detection"
down_revision = "20260616_evidence_retention"
branch_labels = None
depends_on = None

_TS = sa.text("(CURRENT_TIMESTAMP)")


def upgrade() -> None:
    op.create_table(
        "rf_scanners",
        sa.Column("hall_id", sa.Uuid(), nullable=False),
        sa.Column("identifier", sa.String(length=100), nullable=False),
        sa.Column("position", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("api_key_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="offline"),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["hall_id"], ["halls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rf_scanners_hall_id", "rf_scanners", ["hall_id"])

    op.create_table(
        "rf_whitelist_entries",
        sa.Column("hall_id", sa.Uuid(), nullable=False),
        sa.Column("mac_hash", sa.String(length=64), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("device_role", sa.String(length=30), nullable=False, server_default="baseline"),
        sa.Column("baseline_rssi", sa.Integer(), nullable=True),
        sa.Column("added_by", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(["hall_id"], ["halls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rf_whitelist_entries_hall_id", "rf_whitelist_entries", ["hall_id"])
    op.create_index("ix_rf_whitelist_entries_mac_hash", "rf_whitelist_entries", ["mac_hash"])

    op.create_table(
        "rf_detections",
        sa.Column("scanner_id", sa.Uuid(), nullable=False),
        sa.Column("exam_session_id", sa.Uuid(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signal_type", sa.String(length=10), nullable=False),
        sa.Column("mac_hash", sa.String(length=64), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("rssi", sa.Integer(), nullable=True),
        sa.Column("is_whitelisted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("estimated_zone", sa.String(length=100), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(["scanner_id"], ["rf_scanners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exam_session_id"], ["exam_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rf_detections_scanner_id", "rf_detections", ["scanner_id"])
    op.create_index("ix_rf_detections_exam_session_id", "rf_detections", ["exam_session_id"])
    op.create_index("ix_rf_detections_mac_hash", "rf_detections", ["mac_hash"])


def downgrade() -> None:
    op.drop_index("ix_rf_detections_mac_hash", table_name="rf_detections")
    op.drop_index("ix_rf_detections_exam_session_id", table_name="rf_detections")
    op.drop_index("ix_rf_detections_scanner_id", table_name="rf_detections")
    op.drop_table("rf_detections")
    op.drop_index("ix_rf_whitelist_entries_mac_hash", table_name="rf_whitelist_entries")
    op.drop_index("ix_rf_whitelist_entries_hall_id", table_name="rf_whitelist_entries")
    op.drop_table("rf_whitelist_entries")
    op.drop_index("ix_rf_scanners_hall_id", table_name="rf_scanners")
    op.drop_table("rf_scanners")
