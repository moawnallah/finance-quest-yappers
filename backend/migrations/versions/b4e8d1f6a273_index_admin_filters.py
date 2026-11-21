"""index the admin filters added with the insights tables

Revision ID: b4e8d1f6a273
Revises: 8d2f6b1c3e57
Create Date: 2026-11-21 15:30:00

- attempts (submitted_at): the admin overview's "attempts in the last 24 hours".
- feedback (status): the admin feedback list and the open-reports count.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b4e8d1f6a273'
down_revision: Union[str, None] = '8d2f6b1c3e57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_attempts_submitted_at', 'attempts', ['submitted_at'])
    op.create_index('ix_feedback_status', 'feedback', ['status'])


def downgrade() -> None:
    op.drop_index('ix_feedback_status', table_name='feedback')
    op.drop_index('ix_attempts_submitted_at', table_name='attempts')
