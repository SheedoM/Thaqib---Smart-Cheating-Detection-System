"""add multi-tenant institution hierarchy and exam institution_id

Revision ID: 20260609_multi_tenant
Revises: 20260609_role_merge
Create Date: 2026-06-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260609_multi_tenant"
down_revision = "20260609_role_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── institutions: add type + parent_id ───────────────────────────────────
    # batch_alter_table keeps this working on SQLite (no native ALTER ADD FK),
    # while still issuing plain ALTERs on PostgreSQL.
    with op.batch_alter_table("institutions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("type", sa.String(20), nullable=False, server_default="standalone"))
        batch_op.add_column(sa.Column("parent_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_institutions_parent_id",
            "institutions",
            ["parent_id"], ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index("ix_institutions_parent_id", ["parent_id"])

    # ── exam_sessions: add institution_id (nullable for backfill) ────────────
    with op.batch_alter_table("exam_sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("institution_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_exam_sessions_institution_id",
            "institutions",
            ["institution_id"], ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_exam_sessions_institution_id", ["institution_id"])

    bind = op.get_bind()

    # ── backfill exam_sessions.institution_id from halls ────────────────────
    # For each exam_session pick the institution_id of the first linked hall.
    # (One exam = one college enforced going forward; existing data assumed clean.)
    # Correlated subquery references the target table by name (no alias) so the
    # statement is valid on both SQLite and PostgreSQL.
    bind.execute(sa.text("""
        UPDATE exam_sessions
        SET institution_id = (
            SELECT h.institution_id
            FROM exam_session_halls esh
            JOIN halls h ON h.id = esh.hall_id
            WHERE esh.exam_session_id = exam_sessions.id
            LIMIT 1
        )
        WHERE institution_id IS NULL
    """))

    # For sessions with no halls (edge-case), assign the first/only institution.
    bind.execute(sa.text("""
        UPDATE exam_sessions
        SET institution_id = (SELECT id FROM institutions LIMIT 1)
        WHERE institution_id IS NULL
    """))


def downgrade() -> None:
    with op.batch_alter_table("exam_sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_exam_sessions_institution_id")
        batch_op.drop_constraint("fk_exam_sessions_institution_id", type_="foreignkey")
        batch_op.drop_column("institution_id")

    with op.batch_alter_table("institutions", schema=None) as batch_op:
        batch_op.drop_index("ix_institutions_parent_id")
        batch_op.drop_constraint("fk_institutions_parent_id", type_="foreignkey")
        batch_op.drop_column("parent_id")
        batch_op.drop_column("type")
