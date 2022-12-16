"""Cargo shipping method

Revision ID: 98d8ca44873f
Revises: 0f4ca0502c59
Create Date: 2022-12-15 11:18:16.850382

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '98d8ca44873f'
down_revision = '0f4ca0502c59'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE shipping SET discriminator='cargo' WHERE name='Cargo'")
    op.execute("INSERT INTO shipping_params (shipping_id, label, name) VALUES (3, 'Tax ID', 'tax_id')")

def downgrade():
    pass
