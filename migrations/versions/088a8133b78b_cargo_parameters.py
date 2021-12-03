"""Cargo parameters

Revision ID: 088a8133b78b
Revises: bb04eb95150a
Create Date: 2021-12-03 03:08:22.245305

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '088a8133b78b'
down_revision = 'bb04eb95150a'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("INSERT INTO shipping_params (shipping_id, label, name) VALUES (3, 'Passport number', 'passport_number')")


def downgrade():
    pass
