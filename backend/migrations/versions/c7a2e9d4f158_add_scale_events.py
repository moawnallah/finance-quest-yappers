"""add scale_events: Scales kept on the server for real leagues

Revision ID: c7a2e9d4f158
Revises: b4e8d1f6a273
Create Date: 2026-11-21 16:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c7a2e9d4f158'
down_revision: Union[str, None] = 'b4e8d1f6a273'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scale_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('ref', sa.String(60), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id', 'source', 'ref', name='uq_scale_once'),
    )
    op.create_index('ix_scale_events_user_created', 'scale_events', ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_scale_events_user_created', table_name='scale_events')
    op.drop_table('scale_events')
