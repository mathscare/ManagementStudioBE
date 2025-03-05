"""Recreated missing migration

Revision ID: 0e60b77002a2
Revises: eb8e79bfbfa4
Create Date: 2025-03-05 17:22:56.807165

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e60b77002a2'
down_revision: Union[str, None] = 'eb8e79bfbfa4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
