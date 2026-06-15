"""add evidence retention policy fields

Revision ID: 20260616_evidence_retention
Revises: 20260609_multi_tenant
Create Date: 2026-06-16
"""

from __future__ import annotations

from datetime import datetime, timedelta

from alembic import op
import sqlalchemy as sa


revision = "20260616_evidence_retention"
down_revision = "20260609_multi_tenant"
branch_labels = None
depends_on = None


def _add_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year + years)


def _deadline(status: str | None, created_at: datetime | None, confirmed_at: datetime | None, cancelled_at: datetime | None, resolved_at: datetime | None) -> datetime:
    now = datetime.utcnow()
    if status == "confirmed":
        return _add_years(confirmed_at or now, 3)
    if status in {"cancelled", "false_positive"}:
        return (cancelled_at or resolved_at or now) + timedelta(days=30)
    return (created_at or now) + timedelta(days=180)


def upgrade() -> None:
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("evidence_retention_until", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("evidence_purged_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("legal_hold_reason", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("legal_hold_by", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("legal_hold_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key("fk_alerts_legal_hold_by_users", "users", ["legal_hold_by"], ["id"])
        batch_op.create_index("ix_alerts_evidence_retention_until", ["evidence_retention_until"])
        batch_op.create_index("ix_alerts_legal_hold", ["legal_hold"])

    alerts = sa.table(
        "alerts",
        sa.column("id", sa.Uuid()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("confirmed_at", sa.DateTime(timezone=True)),
        sa.column("cancelled_at", sa.DateTime(timezone=True)),
        sa.column("resolved_at", sa.DateTime(timezone=True)),
        sa.column("evidence_retention_until", sa.DateTime(timezone=True)),
    )
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            alerts.c.id,
            alerts.c.status,
            alerts.c.created_at,
            alerts.c.confirmed_at,
            alerts.c.cancelled_at,
            alerts.c.resolved_at,
        )
    )
    for row in rows:
        bind.execute(
            alerts.update()
            .where(alerts.c.id == row.id)
            .values(
                evidence_retention_until=_deadline(
                    row.status,
                    row.created_at,
                    row.confirmed_at,
                    row.cancelled_at,
                    row.resolved_at,
                )
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.drop_index("ix_alerts_legal_hold")
        batch_op.drop_index("ix_alerts_evidence_retention_until")
        batch_op.drop_constraint("fk_alerts_legal_hold_by_users", type_="foreignkey")
        batch_op.drop_column("legal_hold_at")
        batch_op.drop_column("legal_hold_by")
        batch_op.drop_column("legal_hold_reason")
        batch_op.drop_column("legal_hold")
        batch_op.drop_column("evidence_purged_at")
        batch_op.drop_column("evidence_retention_until")
