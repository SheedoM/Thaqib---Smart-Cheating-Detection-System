"""merge referee into admin and add exam admin scoping

Revision ID: 20260609_role_merge
Revises: 20260604_remove_ptt
Create Date: 2026-06-09
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260609_role_merge"
down_revision = "20260604_remove_ptt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exam_admin_assignments",
        sa.Column("exam_session_id", sa.Uuid(), nullable=False),
        sa.Column("admin_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_role", sa.String(length=20), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["exam_session_id"], ["exam_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_session_id", "admin_id", name="uq_exam_admin_assignment"),
    )
    op.create_index(op.f("ix_exam_admin_assignments_id"), "exam_admin_assignments", ["id"], unique=False)

    bind = op.get_bind()
    bind.execute(sa.text("UPDATE users SET role = 'super_admin' WHERE role = 'admin'"))
    bind.execute(sa.text("UPDATE users SET role = 'admin' WHERE role = 'referee'"))

    rows = bind.execute(
        sa.text(
            """
            SELECT e.id, e.created_by
            FROM exam_sessions e
            JOIN users u ON u.id = e.created_by
            WHERE e.created_by IS NOT NULL AND u.role = 'admin'
            """
        )
    ).fetchall()
    for session_id, admin_id in rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO exam_admin_assignments
                    (id, exam_session_id, admin_id, assignment_role, assigned_by)
                VALUES
                    (:id, :exam_session_id, :admin_id, 'lead', :assigned_by)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "exam_session_id": session_id,
                "admin_id": admin_id,
                "assigned_by": admin_id,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE users SET role = 'referee' WHERE role = 'admin'"))
    bind.execute(sa.text("UPDATE users SET role = 'admin' WHERE role = 'super_admin'"))
    op.drop_index(op.f("ix_exam_admin_assignments_id"), table_name="exam_admin_assignments")
    op.drop_table("exam_admin_assignments")
