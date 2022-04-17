"""Sale order status at_warehouse

Revision ID: acaa84d33edc
Revises: 53976c05eb99
Create Date: 2022-04-17 10:11:57.926866

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'acaa84d33edc'
down_revision = '53976c05eb99'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE orders 
        MODIFY COLUMN status SET('draft','pending','can_be_paid','po_created',
                                 'packed','shipped','cancelled','ready_to_ship',
                                 'at_warehouse')""")

def downgrade():
    pass
