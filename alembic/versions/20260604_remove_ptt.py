"""remove push-to-talk: drop ptt_clips, hall_voice_channels, users.ptt_id

Revision ID: 20260604_remove_ptt
Revises: 20260602_hall_voice_channels
Create Date: 2026-06-04

PTT was replaced by a stateless hall voice channel (see api/routes/voice.py) that
keeps no DB state, so the channel/clip tables and the users.ptt_id column are dropped.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260604_remove_ptt"
down_revision = "20260602_hall_voice_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop ptt_clips first (it has FKs into hall_voice_channels).
    op.drop_table("ptt_clips")
    op.drop_table("hall_voice_channels")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("ptt_id")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("ptt_id", sa.String(length=100), nullable=True))

    op.create_table(
        "hall_voice_channels",
        sa.Column("hall_id", sa.Uuid(), nullable=False),
        sa.Column("channel_key", sa.String(length=150), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["hall_id"], ["halls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_key"),
        sa.UniqueConstraint("hall_id"),
    )
    op.create_table(
        "ptt_clips",
        sa.Column("exam_session_id", sa.Uuid(), nullable=False),
        sa.Column("hall_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("speaker_id", sa.Uuid(), nullable=False),
        sa.Column("speaker_role", sa.String(length=20), nullable=False),
        sa.Column("speaker_name", sa.String(length=255), nullable=False),
        sa.Column("clip_type", sa.String(length=20), nullable=False),
        sa.Column("alert_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("audio_file_path", sa.String(length=500), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"]),
        sa.ForeignKeyConstraint(["channel_id"], ["hall_voice_channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exam_session_id"], ["exam_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hall_id"], ["halls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["speaker_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
