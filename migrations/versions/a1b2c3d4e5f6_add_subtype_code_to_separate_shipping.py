"""Add subtype_code to SeparateShipping

Revision ID: a1b2c3d4e5f6
Revises: f822172d5329
Create Date: 2026-04-07

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f822172d5329'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('shipping', sa.Column('subtype_code', sa.String(16), nullable=True))


def downgrade():
    op.drop_column('shipping', 'subtype_code')
