"""Add box dimension columns to shipments

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('shipments', sa.Column('length_cm', sa.Numeric(6, 1), nullable=True))
    op.add_column('shipments', sa.Column('width_cm',  sa.Numeric(6, 1), nullable=True))
    op.add_column('shipments', sa.Column('height_cm', sa.Numeric(6, 1), nullable=True))


def downgrade() -> None:
    op.drop_column('shipments', 'height_cm')
    op.drop_column('shipments', 'width_cm')
    op.drop_column('shipments', 'length_cm')
