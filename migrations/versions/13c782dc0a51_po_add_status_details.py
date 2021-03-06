"""PO: add status details

Revision ID: 13c782dc0a51
Revises: 167b16148b7c
Create Date: 2020-10-15 20:05:15.783136

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '13c782dc0a51'
down_revision = '167b16148b7c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('orders', 'status',
               existing_type=mysql.SET(collation='utf8_unicode_ci', length=10),
               type_=sa.Enum('pending', 'paid', 'po_created', 'shipped', 'complete', name='orderstatus'),
               existing_nullable=True)
    op.add_column('purchase_orders', sa.Column('status_details', sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('purchase_orders', 'status_details')
    op.alter_column('orders', 'status',
               existing_type=sa.Enum('pending', 'paid', 'po_created', 'shipped', 'complete', name='orderstatus'),
               type_=mysql.SET(collation='utf8_unicode_ci', length=10),
               existing_nullable=True)
    # ### end Alembic commands ###
