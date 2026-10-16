"""Suborder vendor

Revision ID: e1e4f5a6b7c8
Revises: d9d3e4f5a6b7
Create Date: 2026-10-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1e4f5a6b7c8'
down_revision = 'd9d3e4f5a6b7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('suborders', sa.Column(
        'vendor', sa.String(length=16), nullable=False, server_default='Atomy'))
    # Suborders created before have products of a single vendor in practice.
    # Take the vendor of the products for non-Atomy ones
    op.get_bind().execute(sa.text("""
        UPDATE suborders s
        JOIN order_products op ON op.suborder_id = s.id
        SET s.vendor = op.product_vendor
        WHERE op.product_vendor <> 'Atomy'
    """))


def downgrade():
    op.drop_column('suborders', 'vendor')
