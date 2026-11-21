"""add onboarding, reco_events, llm_events, feedback, consents; hard-task fields on attempts

Revision ID: 7c1e5a9d2b40
Revises: 46f9cd038a2b
Create Date: 2026-11-21 12:00:00

docs/admin_and_profile.md
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '7c1e5a9d2b40'
down_revision: Union[str, None] = '46f9cd038a2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('attempts', schema=None) as b:
        b.add_column(sa.Column('points', sa.Integer(), nullable=True))
        b.add_column(sa.Column('growth_index', sa.Float(), nullable=True))
        b.add_column(sa.Column('failed_test', sa.String(length=200), nullable=True))
        b.add_column(sa.Column('duration_ms', sa.Integer(), nullable=True))

    op.create_table('onboarding',
                    sa.Column('user_id', sa.String(length=36), nullable=False),
                    sa.Column('survey', sa.JSON(), nullable=False),
                    sa.Column('result', sa.JSON(), nullable=False),
                    sa.Column('router_version', sa.String(length=20), nullable=False),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('user_id'))

    op.create_table('reco_events',
                    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
                    sa.Column('user_id', sa.String(length=36), nullable=True),
                    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('router_version', sa.String(length=20), nullable=False),
                    sa.Column('event_type', sa.String(length=40), nullable=False),
                    sa.Column('node', sa.String(length=10), nullable=True),
                    sa.Column('payload', sa.JSON(), nullable=False),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_reco_events_user_id', 'reco_events', ['user_id'])
    op.create_index('ix_reco_events_event_type', 'reco_events', ['event_type'])

    op.create_table('llm_events',
                    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
                    sa.Column('user_id', sa.String(length=36), nullable=True),
                    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('payload', sa.JSON(), nullable=False),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_llm_events_user_id', 'llm_events', ['user_id'])

    op.create_table('feedback',
                    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
                    sa.Column('user_id', sa.String(length=36), nullable=True),
                    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('where', sa.String(length=20), nullable=False),
                    sa.Column('target_id', sa.String(length=60), nullable=False),
                    sa.Column('kind', sa.String(length=20), nullable=False),
                    sa.Column('rating', sa.Integer(), nullable=True),
                    sa.Column('text', sa.Text(), nullable=True),
                    sa.Column('status', sa.String(length=20), nullable=False),
                    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
                    sa.CheckConstraint("status IN ('new','triaged','fixed','wont_fix')", name='ck_feedback_status'),
                    sa.CheckConstraint('rating IS NULL OR rating BETWEEN 1 AND 5', name='ck_feedback_rating'),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_feedback_user_id', 'feedback', ['user_id'])
    op.create_index('ix_feedback_target_id', 'feedback', ['target_id'])

    op.create_table('consents',
                    sa.Column('participant_id', sa.String(length=12), nullable=False),
                    sa.Column('user_id', sa.String(length=36), nullable=False),
                    sa.Column('consent_version', sa.String(length=20), nullable=False),
                    sa.Column('given_at', sa.DateTime(timezone=True), nullable=False),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('participant_id'),
                    sa.UniqueConstraint('user_id'))


def downgrade() -> None:
    op.drop_table('consents')
    op.drop_index('ix_feedback_target_id', table_name='feedback')
    op.drop_index('ix_feedback_user_id', table_name='feedback')
    op.drop_table('feedback')
    op.drop_index('ix_llm_events_user_id', table_name='llm_events')
    op.drop_table('llm_events')
    op.drop_index('ix_reco_events_event_type', table_name='reco_events')
    op.drop_index('ix_reco_events_user_id', table_name='reco_events')
    op.drop_table('reco_events')
    op.drop_table('onboarding')
    with op.batch_alter_table('attempts', schema=None) as b:
        b.drop_column('duration_ms')
        b.drop_column('failed_test')
        b.drop_column('growth_index')
        b.drop_column('points')
