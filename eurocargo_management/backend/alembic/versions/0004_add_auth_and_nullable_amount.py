"""Add auth columns to users and make amount_eur nullable

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Auth columns — nullable so existing rows are unaffected
    op.add_column('users',
                  sa.Column('password_hash', sa.String(128), nullable=True))
    op.add_column('users',
                  sa.Column('role', sa.String(32), nullable=True))

    # amount_eur is now calculated at creation time but may not always be present
    op.alter_column('shipments', 'amount_eur', nullable=True)


def downgrade() -> None:
    op.alter_column('shipments', 'amount_eur', nullable=False)
    op.drop_column('users', 'role')
    op.drop_column('users', 'password_hash')
