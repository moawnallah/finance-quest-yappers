"""users.share_profile (consent) and users.synthetic (demo data)

Revision ID: e8a4b2d6f013
Revises: d3f7a1c9e284
Create Date: 2026-11-21 22:30:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e8a4b2d6f013'
down_revision: Union[str, None] = 'd3f7a1c9e284'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as b:
        b.add_column(sa.Column('share_profile', sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column('synthetic', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table('users') as b:
        b.drop_column('synthetic')
        b.drop_column('share_profile')
