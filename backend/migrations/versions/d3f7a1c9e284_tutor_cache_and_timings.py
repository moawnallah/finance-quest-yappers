"""tutor answer cache and Ollama timings in llm_events

Revision ID: d3f7a1c9e284
Revises: c7a2e9d4f158
Create Date: 2026-11-21 22:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd3f7a1c9e284'
down_revision: Union[str, None] = 'c7a2e9d4f158'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('llm_events') as b:
        b.add_column(sa.Column('load_ms', sa.Integer(), nullable=True))
        b.add_column(sa.Column('prompt_eval_ms', sa.Integer(), nullable=True))
        b.add_column(sa.Column('eval_ms', sa.Integer(), nullable=True))
    op.create_table(
        'tutor_cache',
        sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('mode', sa.String(30), nullable=False),
        sa.Column('node', sa.String(10), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('mermaid', sa.Text(), nullable=True),
        sa.Column('hits', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('tutor_cache')
    with op.batch_alter_table('llm_events') as b:
        b.drop_column('eval_ms')
        b.drop_column('prompt_eval_ms')
        b.drop_column('load_ms')
