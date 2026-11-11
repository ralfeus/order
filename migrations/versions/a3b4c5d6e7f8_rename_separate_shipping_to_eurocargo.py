"""Rename SeparateShipping to EurocargoShipping

Changes the polymorphic identity of existing shipping methods from
'separate' to 'eurocargo' and removes the obsolete per-method first-leg
rate and shipper currency settings (Eurocargo prices the first leg itself).

Revision ID: a3b4c5d6e7f8
Revises: f2f5a6b7c8d9
Create Date: 2026-11-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3b4c5d6e7f8'
down_revision = 'f2f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE shipping SET discriminator = 'eurocargo' "
               "WHERE discriminator = 'separate'")
    settings = sa.table('settings', sa.column('key', sa.String))
    op.execute(settings.delete().where(settings.c.key.like('shipping.separate.%')))


def downgrade():
    # The deleted first_leg / currency settings are not restored: they are
    # optional and were unused by the time of this migration.
    op.execute("UPDATE shipping SET discriminator = 'separate' "
               "WHERE discriminator = 'eurocargo'")
