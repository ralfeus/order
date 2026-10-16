"""Default purchase order vendor settings

Revision ID: f2f5a6b7c8d9
Revises: e1e4f5a6b7c8
Create Date: 2026-10-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2f5a6b7c8d9'
down_revision = 'e1e4f5a6b7c8'
branch_labels = None
depends_on = None

SETTINGS = {
    'purchase.default_vendor.Atomy': 'AtomyQuick',
    'purchase.default_vendor.AtomyAza': '',
}


def upgrade():
    for key, value in SETTINGS.items():
        op.get_bind().execute(sa.text("""
            INSERT INTO settings (when_created, `key`, value, default_value, description)
            VALUES (NOW(), :key, :value, :value, :description)
        """), {
            'key': key,
            'value': value,
            'description': f'Purchase order vendor used by default for products of '
                           f'{key.split(".")[-1]}. Empty - must be chosen on PO creation'
        })


def downgrade():
    for key in SETTINGS:
        op.get_bind().execute(sa.text("DELETE FROM settings WHERE `key` = :key"), {'key': key})
