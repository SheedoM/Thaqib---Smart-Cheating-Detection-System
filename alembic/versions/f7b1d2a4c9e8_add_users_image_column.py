"""add users.image column

Revision ID: f7b1d2a4c9e8
Revises: ce3587b4e14d
Create Date: 2026-05-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7b1d2a4c9e8"
down_revision: Union[str, Sequence[str], None] = "ce3587b4e14d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("image", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("image")
