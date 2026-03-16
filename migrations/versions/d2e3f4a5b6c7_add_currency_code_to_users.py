"""Add currency_code to users table

Revision ID: d2e3f4a5b6c7
Revises: c2d3e4f5a6b7
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'd2e3f4a5b6c7'
down_revision = 'c2d3e4f5a6b7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users',
        sa.Column('currency_code', sa.String(3), sa.ForeignKey('currencies.code'), nullable=True))
    # Populate from existing profile JSON where currency is set
    op.execute("""
        UPDATE users
        SET currency_code = JSON_UNQUOTE(JSON_EXTRACT(profile, '$.currency'))
        WHERE JSON_EXTRACT(profile, '$.currency') IS NOT NULL
          AND JSON_UNQUOTE(JSON_EXTRACT(profile, '$.currency')) IN (SELECT code FROM currencies)
    """)


def downgrade():
    op.drop_column('users', 'currency_code')
