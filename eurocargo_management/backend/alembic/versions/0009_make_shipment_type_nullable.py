"""Make shipment_type_id nullable (carrier chosen at payment time, not creation)

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-12
"""
from alembic import op

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('shipments', 'shipment_type_id', nullable=True)


def downgrade() -> None:
    # Re-applying NOT NULL requires all rows to have a value; assumes data is clean.
    op.alter_column('shipments', 'shipment_type_id', nullable=False)
