"""Set address_id in PurchaseOrder

Revision ID: 5a9a1e0450a6
Revises: d41fcb00aa71
Create Date: 2021-07-11 11:55:06.211085

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5a9a1e0450a6'
down_revision = 'd41fcb00aa71'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE purchase_orders AS po JOIN addresses AS ad ON po.address_1 = ad.address_1 
        SET po.address_id = ad.id
    """)


def downgrade():
    pass
