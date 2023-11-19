"""EMS separate method

Revision ID: 0e0653183508
Revises: 58dbba4ccddd
Create Date: 2023-11-19 12:32:47.384032

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0e0653183508'
down_revision = '58dbba4ccddd'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE shipping SET discriminator = 'ems' WHERE id = 1")


def downgrade():
    op.execute("UPDATE shipping SET discriminator = NULL WHERE id = 1")
