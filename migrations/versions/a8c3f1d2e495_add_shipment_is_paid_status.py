"""add shipment_is_paid order status

Revision ID: a8c3f1d2e495
Revises: b506960fac58
Create Date: 2026-02-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'a8c3f1d2e495'
down_revision = 'b506960fac58'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'orders', 'status',
        existing_type=mysql.ENUM(
            'draft', 'pending', 'can_be_paid', 'po_created', 'packed',
            'shipped', 'cancelled', 'ready_to_ship', 'at_warehouse'
        ),
        type_=mysql.ENUM(
            'draft', 'pending', 'can_be_paid', 'po_created', 'packed',
            'shipped', 'cancelled', 'ready_to_ship', 'at_warehouse', 'shipment_is_paid'
        ),
        existing_nullable=True
    )


def downgrade():
    op.alter_column(
        'orders', 'status',
        existing_type=mysql.ENUM(
            'draft', 'pending', 'can_be_paid', 'po_created', 'packed',
            'shipped', 'cancelled', 'ready_to_ship', 'at_warehouse', 'shipment_is_paid'
        ),
        type_=mysql.ENUM(
            'draft', 'pending', 'can_be_paid', 'po_created', 'packed',
            'shipped', 'cancelled', 'ready_to_ship', 'at_warehouse'
        ),
        existing_nullable=True
    )
