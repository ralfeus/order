"""AtomyAza import categories setting

Revision ID: d9d3e4f5a6b7
Revises: c8b2d3e4f5a6
Create Date: 2026-10-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd9d3e4f5a6b7'
down_revision = 'c8b2d3e4f5a6'
branch_labels = None
depends_on = None

KEY = 'product_import.aza.categories'


def upgrade():
    op.get_bind().execute(sa.text("""
        INSERT INTO settings (when_created, `key`, value, default_value, description)
        VALUES (NOW(), :key, '', '', :description)
    """), {
        'key': KEY,
        'description': 'AtomyAza categories (ca_id) to import products from, '
                       'separated by commas. Top level category (e.g. 011) includes '
                       'all its subcategories. Empty - no import'
    })


def downgrade():
    op.get_bind().execute(sa.text("DELETE FROM settings WHERE `key` = :key"), {'key': KEY})
