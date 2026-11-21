"""add llm_events and reco_events (admin monitoring)

Revision ID: 7b3e9c1d4a20
Revises: 46f9cd038a2b
Create Date: 2026-11-21 12:30:00

Tables for the admin panel (docs/tutor_agent.md, sections 5 and 6): every
tutor/router model call and every recommender event. Text is stored masked.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '7b3e9c1d4a20'
down_revision: Union[str, None] = '46f9cd038a2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'llm_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('screen_id', sa.String(length=60), nullable=True),
        sa.Column('task_id', sa.String(length=40), nullable=True),
        sa.Column('node', sa.String(length=10), nullable=True),
        sa.Column('mode', sa.String(length=30), nullable=True),
        sa.Column('intent', sa.String(length=30), nullable=True),
        sa.Column('model_role', sa.String(length=30), nullable=True),
        sa.Column('model', sa.String(length=80), nullable=True),
        sa.Column('prompt_version', sa.String(length=30), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('tokens_in', sa.Integer(), nullable=True),
        sa.Column('tokens_out', sa.Integer(), nullable=True),
        sa.Column('checks_failed', sa.JSON(), nullable=False),
        sa.Column('fallback_used', sa.Boolean(), nullable=False),
        sa.Column('hint_level', sa.Integer(), nullable=True),
        sa.Column('user_rating', sa.Integer(), nullable=True),
        sa.Column('flagged_for_review', sa.Boolean(), nullable=False),
        sa.Column('prompt_masked', sa.Text(), nullable=True),
        sa.Column('answer_masked', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_llm_events_ts', 'llm_events', ['ts'])
    op.create_index('ix_llm_events_user_id', 'llm_events', ['user_id'])
    op.create_index('ix_llm_events_node', 'llm_events', ['node'])
    op.create_index('ix_llm_events_intent', 'llm_events', ['intent'])
    op.create_index('ix_llm_events_flagged_for_review', 'llm_events', ['flagged_for_review'])

    op.create_table(
        'reco_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('router_version', sa.String(length=30), nullable=True),
        sa.Column('event_type', sa.String(length=40), nullable=False),
        sa.Column('node', sa.String(length=10), nullable=True),
        sa.Column('predicted_m', sa.Float(), nullable=True),
        sa.Column('observed', sa.Integer(), nullable=True),
        sa.Column('need', sa.Float(), nullable=True),
        sa.Column('overconfidence_term', sa.Float(), nullable=True),
        sa.Column('interest_term', sa.Float(), nullable=True),
        sa.Column('priority', sa.Float(), nullable=True),
        sa.Column('reason_term', sa.String(length=60), nullable=True),
        sa.Column('path', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reco_events_ts', 'reco_events', ['ts'])
    op.create_index('ix_reco_events_user_id', 'reco_events', ['user_id'])
    op.create_index('ix_reco_events_event_type', 'reco_events', ['event_type'])


def downgrade() -> None:
    op.drop_table('reco_events')
    op.drop_table('llm_events')
