"""add hall voice channels and ptt clips

Revision ID: 20260602_hall_voice_channels
Revises: 20260528_alert_review_lifecycle
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa
import uuid


revision = "20260602_hall_voice_channels"
down_revision = "20260528_alert_review_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.create_index(
        op.f("ix_hall_voice_channels_id"),
        "hall_voice_channels",
        ["id"],
        unique=False,
    )
    bind = op.get_bind()
    halls = bind.execute(sa.text("SELECT id FROM halls WHERE deleted_at IS NULL")).fetchall()
    for hall in halls:
        hall_id = hall[0]
        bind.execute(
            sa.text(
                """
                INSERT INTO hall_voice_channels (id, hall_id, channel_key, status)
                VALUES (:id, :hall_id, :channel_key, :status)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "hall_id": hall_id,
                "channel_key": f"hall:{hall_id}",
                "status": "active",
            },
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
    op.create_index(op.f("ix_ptt_clips_id"), "ptt_clips", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ptt_clips_id"), table_name="ptt_clips")
    op.drop_table("ptt_clips")
    op.drop_index(op.f("ix_hall_voice_channels_id"), table_name="hall_voice_channels")
    op.drop_table("hall_voice_channels")
