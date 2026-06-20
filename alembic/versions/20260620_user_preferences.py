"""add user dashboard preferences

Revision ID: 20260620_user_preferences
Revises: 20260617_rf_detection
Create Date: 2026-06-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260620_user_preferences"
down_revision = "20260617_rf_detection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("preferences", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("preferences")
