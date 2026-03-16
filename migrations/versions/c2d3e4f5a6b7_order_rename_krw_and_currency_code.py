"""Rename *_krw to *_base_currency and currency_code to user_currency_code in orders

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'c2d3e4f5a6b7'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('orders', 'subtotal_krw',
                    existing_type=mysql.INTEGER(),
                    new_column_name='subtotal_base_currency')
    op.alter_column('orders', 'shipping_krw',
                    existing_type=mysql.INTEGER(),
                    new_column_name='shipping_base_currency')
    op.alter_column('orders', 'total_krw',
                    existing_type=mysql.INTEGER(),
                    new_column_name='total_base_currency')
    op.alter_column('orders', 'currency_code',
                    existing_type=mysql.VARCHAR(3),
                    new_column_name='user_currency_code')


def downgrade():
    op.alter_column('orders', 'user_currency_code',
                    existing_type=mysql.VARCHAR(3),
                    new_column_name='currency_code')
    op.alter_column('orders', 'total_base_currency',
                    existing_type=mysql.INTEGER(),
                    new_column_name='total_krw')
    op.alter_column('orders', 'shipping_base_currency',
                    existing_type=mysql.INTEGER(),
                    new_column_name='shipping_krw')
    op.alter_column('orders', 'subtotal_base_currency',
                    existing_type=mysql.INTEGER(),
                    new_column_name='subtotal_krw')
