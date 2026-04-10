"""Add multiplier column to shipment_types (carriers)

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'shipment_types',
        sa.Column('multiplier', sa.Numeric(10, 4), nullable=False, server_default='1.0'),
    )


def downgrade() -> None:
    op.drop_column('shipment_types', 'multiplier')
