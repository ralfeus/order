"""Product vendor

Revision ID: b7a1c2d3e4f5
Revises: 76c858efbf76
Create Date: 2026-09-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7a1c2d3e4f5'
down_revision = '76c858efbf76'
branch_labels = None
depends_on = None


def upgrade():
    # All existing products come from Atomy catalog
    op.add_column('products', sa.Column(
        'vendor', sa.String(16), nullable=False, server_default='Atomy'))
    op.create_index(op.f('ix_products_vendor'), 'products', ['vendor'])


def downgrade():
    conn = op.get_bind()
    other_vendors = conn.execute(sa.text(
        "SELECT COUNT(*) FROM products WHERE vendor <> 'Atomy'")).scalar()
    if other_vendors:
        raise Exception(
            f"Can't downgrade: there are {other_vendors} products of vendors other than Atomy")
    op.drop_index(op.f('ix_products_vendor'), table_name='products')
    op.drop_column('products', 'vendor')
