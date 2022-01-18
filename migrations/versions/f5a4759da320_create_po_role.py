"""Create PO role

Revision ID: f5a4759da320
Revises: 72d51a812c18
Create Date: 2022-01-14 10:32:24.812279

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5a4759da320'
down_revision = '72d51a812c18'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("INSERT INTO roles (name) VALUES ('allow_create_po')")


def downgrade():
    pass
