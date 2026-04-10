"""Add user currency to orders

Replaces the hardcoded cur1 (USD) / cur2 (EUR) secondary currency columns
with a single user-selected currency column and matching amount fields.

Revision ID: b1c2d3e4f5a6
Revises: a1743bf06a76
Create Date: 2026-03-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = 'a8c3f1d2e495'
branch_labels = None
depends_on = None


def upgrade():
    # Add user-selected currency code column
    op.add_column('orders', sa.Column('currency_code', sa.String(length=3), nullable=True))
    op.create_foreign_key(
        'fk_orders_currency_code', 'orders', 'currencies', ['currency_code'], ['code']
    )

    # Rename cur1 columns (previously hardcoded USD) to user_currency
    op.alter_column('orders', 'subtotal_cur1',
                    existing_type=mysql.NUMERIC(10, 2), new_column_name='subtotal_user_currency')
    op.alter_column('orders', 'shipping_cur1',
                    existing_type=mysql.NUMERIC(10, 2), new_column_name='shipping_user_currency')
    op.alter_column('orders', 'total_cur1',
                    existing_type=mysql.NUMERIC(10, 2), new_column_name='total_user_currency')

    # Populate currency_code for existing orders (they were USD = cur1)
    op.execute("UPDATE orders SET currency_code = 'USD' WHERE currency_code IS NULL")

    # Drop the hardcoded cur2 (EUR) columns
    op.drop_column('orders', 'subtotal_cur2')
    op.drop_column('orders', 'shipping_cur2')
    op.drop_column('orders', 'total_cur2')


def downgrade():
    # Restore cur2 columns (EUR)
    op.add_column('orders', sa.Column('subtotal_cur2', mysql.NUMERIC(10, 2), nullable=True))
    op.add_column('orders', sa.Column('shipping_cur2', mysql.NUMERIC(10, 2), nullable=True))
    op.add_column('orders', sa.Column('total_cur2', mysql.NUMERIC(10, 2), nullable=True))

    # Rename user_currency columns back to cur1
    op.alter_column('orders', 'subtotal_user_currency',
                    existing_type=mysql.NUMERIC(10, 2), new_column_name='subtotal_cur1')
    op.alter_column('orders', 'shipping_user_currency',
                    existing_type=mysql.NUMERIC(10, 2), new_column_name='shipping_cur1')
    op.alter_column('orders', 'total_user_currency',
                    existing_type=mysql.NUMERIC(10, 2), new_column_name='total_cur1')

    # Drop currency_code column
    op.drop_constraint('fk_orders_currency_code', 'orders', type_='foreignkey')
    op.drop_column('orders', 'currency_code')
