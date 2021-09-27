"""empty message

Revision ID: 365109f929b6
Revises: b724fe040186
Create Date: 2021-08-06 11:35:50.197519

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '365109f929b6'
down_revision = 'b724fe040186'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE orders MODIFY COLUMN status enum('draft','pending','can_be_paid','po_created','packed','shipped','cancelled','ready_to_ship')")


def downgrade():
    pass
