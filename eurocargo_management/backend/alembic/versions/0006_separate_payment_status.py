"""Separate payment status from shipment status

Adds a boolean `paid` column and migrates the old status values:
  pending  → incoming
  paid     → incoming + paid=true
  shipped  → shipped + paid=true (assumed paid if already shipped)

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add paid column (temporarily nullable so we can back-fill)
    op.add_column('shipments',
                  sa.Column('paid', sa.Boolean(), nullable=True, server_default='false'))

    # Widen status column to hold new longer values
    op.alter_column('shipments', 'status',
                    type_=sa.String(32), existing_type=sa.String(16))

    # Migrate old status values
    op.execute("""
        UPDATE shipments SET paid = true, status = 'incoming'
        WHERE status = 'paid'
    """)
    op.execute("""
        UPDATE shipments SET paid = true
        WHERE status = 'shipped'
    """)
    op.execute("""
        UPDATE shipments SET status = 'incoming'
        WHERE status = 'pending'
    """)

    # Now make paid NOT NULL
    op.alter_column('shipments', 'paid', nullable=False)


def downgrade() -> None:
    # Reverse: collapse paid + status back into old status values
    op.execute("""
        UPDATE shipments SET status = 'paid'
        WHERE paid = true AND status = 'incoming'
    """)
    op.execute("""
        UPDATE shipments SET status = 'pending'
        WHERE paid = false AND status = 'incoming'
    """)
    op.alter_column('shipments', 'status',
                    type_=sa.String(16), existing_type=sa.String(32))
    op.drop_column('shipments', 'paid')
