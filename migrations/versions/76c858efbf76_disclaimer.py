"""Disclaimer

Revision ID: 76c858efbf76
Revises: fa01a9d1354f
Create Date: 2026-04-21 09:02:36.038104

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '76c858efbf76'
down_revision = 'fa01a9d1354f'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE settings
        MODIFY COLUMN value TEXT
    """)
    op.execute("""
        INSERT INTO settings (when_created, `key`, value)
        VALUES (NOW(), 'order.new.disclaimer', '')
    """)


def downgrade():
    op.execute("""
        DELETE FROM settings WHERE `key` = 'order.new.disclaimer'
    """)
