"""llm_events.review_label and reviewed_at: a reviewer's label on a flagged tutor answer

Revision ID: f5c1d9a7b230
Revises: e8a4b2d6f013
Create Date: 2026-11-22 10:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f5c1d9a7b230'
down_revision: Union[str, None] = 'e8a4b2d6f013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('llm_events') as b:
        b.add_column(sa.Column('review_label', sa.String(length=20), nullable=True))
        b.add_column(sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('llm_events') as b:
        b.drop_column('reviewed_at')
        b.drop_column('review_label')
