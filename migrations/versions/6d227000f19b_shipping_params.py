"""EMS shipping params

Revision ID: 6d227000f19b
Revises: 0e0653183508
Create Date: 2023-11-25 12:38:04.391050

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6d227000f19b'
down_revision = '0e0653183508'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO shipping_params 
            (when_created, shipping_id, label, name, type) 
            SELECT 
                NOW(), id, 
               'Declared shipping items\nOne item per line\nEach line in format _name_|_qty_|_price_', 
               'items', 'multiline'
            FROM shipping
    """)


def downgrade():
    op.execute("DELETE FROM shipping_params WHERE shipping_id = 1")
