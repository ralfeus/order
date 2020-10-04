"""invoice customer name

Revision ID: 166a85d1f865
Revises: b6ccd90b4c43
Create Date: 2020-09-30 18:07:53.316484

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '166a85d1f865'
down_revision = 'b6ccd90b4c43'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('invoices', sa.Column('customer', sa.String(length=128), nullable=True))
    op.drop_column('invoices', 'name')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('invoices', sa.Column('name', mysql.VARCHAR(collation='utf8_unicode_ci', length=128), nullable=True))
    op.drop_column('invoices', 'customer')
    # ### end Alembic commands ###