"""add email and password accounts to users

Revision ID: 9c4d2e7f1a31
Revises: 7b3e9c1d4a20
Create Date: 2026-11-21 15:00:00

Adds users.email (unique, lower case), users.password_hash (scrypt, see
app/auth.py), users.is_admin and users.last_login_at. Existing anonymous
sessions keep NULL email and password. batch_alter_table keeps SQLite happy.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '9c4d2e7f1a31'
down_revision: Union[str, None] = '7b3e9c1d4a20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as b:
        b.add_column(sa.Column('email', sa.String(length=254), nullable=True))
        b.add_column(sa.Column('password_hash', sa.String(length=255), nullable=True))
        b.add_column(sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
        b.create_index('ix_users_email', ['email'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('users') as b:
        b.drop_index('ix_users_email')
        b.drop_column('last_login_at')
        b.drop_column('is_admin')
        b.drop_column('password_hash')
        b.drop_column('email')
