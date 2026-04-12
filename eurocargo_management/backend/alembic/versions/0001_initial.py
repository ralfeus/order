"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'shipment_types',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(16), nullable=False, unique=True),
        sa.Column('name', sa.String(64), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
    )

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(128), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    op.create_table(
        'shipments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('token', sa.String(64), nullable=False, unique=True),
        sa.Column('order_id', sa.String(32), nullable=False, unique=True),
        sa.Column('customer_name', sa.String(128), nullable=False),
        sa.Column('email', sa.String(128), nullable=False),
        sa.Column('address', sa.String(256), nullable=False),
        sa.Column('city', sa.String(128), nullable=False),
        sa.Column('country', sa.String(2), nullable=False),
        sa.Column('zip', sa.String(16), nullable=False),
        sa.Column('phone', sa.String(32), nullable=True),
        sa.Column('shipment_type_id', sa.Integer(),
                  sa.ForeignKey('shipment_types.id'), nullable=False),
        sa.Column('tracking_code', sa.String(64), nullable=True),
        sa.Column('amount_eur', sa.Numeric(10, 2), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('shipment_id', sa.Integer(),
                  sa.ForeignKey('shipments.id'), nullable=False),
        sa.Column('revolut_order_id', sa.String(64), nullable=True, unique=True),
        sa.Column('method', sa.String(16), nullable=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
        sa.Column('amount_eur', sa.Numeric(10, 2), nullable=False),
        sa.Column('checkout_url', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('payments')
    op.drop_table('shipments')
    op.drop_table('users')
    op.drop_table('shipment_types')
