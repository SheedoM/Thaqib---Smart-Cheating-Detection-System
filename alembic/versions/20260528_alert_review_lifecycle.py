"""add alert review lifecycle fields

Revision ID: 20260528_alert_review_lifecycle
Revises: 63345f4ffba2
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa


revision = "20260528_alert_review_lifecycle"
down_revision = "63345f4ffba2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("confirmed_by", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("cancelled_by", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key("fk_alerts_confirmed_by_users", "users", ["confirmed_by"], ["id"])
        batch_op.create_foreign_key("fk_alerts_cancelled_by_users", "users", ["cancelled_by"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.drop_constraint("fk_alerts_cancelled_by_users", type_="foreignkey")
        batch_op.drop_constraint("fk_alerts_confirmed_by_users", type_="foreignkey")
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("cancelled_by")
        batch_op.drop_column("confirmed_at")
        batch_op.drop_column("confirmed_by")
