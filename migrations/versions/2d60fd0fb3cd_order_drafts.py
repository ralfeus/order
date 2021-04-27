"""order drafts

Revision ID: 2d60fd0fb3cd
Revises: 8c9957eafdb4
Create Date: 2021-04-21 19:53:43.694764

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '2d60fd0fb3cd'
down_revision = '8c9957eafdb4'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('orders', 'status',
        existing_type=mysql.ENUM('pending','can_be_paid','po_created','packed','shipped','cancelled', collation='utf8_unicode_ci'),
        type_=sa.Enum('draft', 'pending','can_be_paid','po_created','packed','shipped','cancelled', name='orderstatus'),
        existing_nullable=True)
    op.execute('UPDATE orders SET status=\'draft\' WHERE id LIKE \'%draft%\'')


def downgrade():
    pass
