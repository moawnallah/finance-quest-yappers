"""add indexes for the most frequent queries

Revision ID: a1f3c5e8b902
Revises: 9c4d2e7f1a31
Create Date: 2026-11-21 16:30:00

- answers (user_id, created_at): weekly XP for the league and the streak.
- events (created_at): admin "last 24 hours" counts.
- users (created_at): league membership is ordered by sign-up time.
Lookups by token, email, attempts (user, node), events (user, name) and the
LLM/recommender logs were already indexed.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a1f3c5e8b902'
down_revision: Union[str, None] = '9c4d2e7f1a31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_answers_user_created', 'answers', ['user_id', 'created_at'])
    op.create_index('ix_events_created_at', 'events', ['created_at'])
    op.create_index('ix_users_created_at', 'users', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_users_created_at', table_name='users')
    op.drop_index('ix_events_created_at', table_name='events')
    op.drop_index('ix_answers_user_created', table_name='answers')
