"""merge users image and assignment monitoring heads

Revision ID: 63345f4ffba2
Revises: c3a2ebcd87b1, f7b1d2a4c9e8
Create Date: 2026-05-20 21:06:00.744307

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '63345f4ffba2'
down_revision: Union[str, Sequence[str], None] = ('c3a2ebcd87b1', 'f7b1d2a4c9e8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
