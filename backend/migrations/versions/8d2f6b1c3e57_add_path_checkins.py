"""add path_checkins (the end-of-path check-in)

Revision ID: 8d2f6b1c3e57
Revises: 7c1e5a9d2b40
Create Date: 2026-11-21 14:00:00

docs/admin_and_profile.md, "Demo mode and the end of a path"
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '8d2f6b1c3e57'
down_revision: Union[str, None] = '7c1e5a9d2b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('path_checkins',
                    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
                    sa.Column('user_id', sa.String(length=36), nullable=False),
                    sa.Column('path_id', sa.String(length=30), nullable=False),
                    sa.Column('answers', sa.JSON(), nullable=False),
                    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_path_checkins_user_id', 'path_checkins', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_path_checkins_user_id', table_name='path_checkins')
    op.drop_table('path_checkins')
