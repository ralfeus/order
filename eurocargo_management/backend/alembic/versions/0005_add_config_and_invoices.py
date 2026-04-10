"""Add config and invoices tables; drop payments table

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    op.create_table(
        'invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_number', sa.String(32), nullable=False),
        sa.Column('shipment_id', sa.Integer(), nullable=False),
        sa.Column('pdf_data', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_number'),
        sa.UniqueConstraint('shipment_id'),
    )

    # Seed default config keys — values left NULL until the operator fills them in
    op.execute("""
        INSERT INTO config (name, value) VALUES
            ('invoice_prefix',       'INV'),
            ('recipient_name',       NULL),
            ('recipient_address',    NULL),
            ('recipient_vat',        NULL),
            ('recipient_iban',       NULL),
            ('recipient_bic',        NULL),
            ('recipient_bank_name',  NULL)
    """)

    op.drop_table('payments')


def downgrade() -> None:
    op.drop_table('invoices')
    op.drop_table('config')
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shipment_id', sa.Integer(), nullable=False),
        sa.Column('revolut_order_id', sa.String(128), nullable=True),
        sa.Column('method', sa.String(16), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('amount_eur', sa.Numeric(10, 2), nullable=False),
        sa.Column('checkout_url', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id']),
        sa.PrimaryKeyConstraint('id'),
    )
