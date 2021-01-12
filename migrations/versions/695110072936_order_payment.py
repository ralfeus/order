"""order payment

Revision ID: 695110072936
Revises: 4c761fd374bc
Create Date: 2020-12-17 08:59:35.602245

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '695110072936'
down_revision = '4c761fd374bc'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('orders', sa.Column('transaction_id', sa.Integer(), nullable=True))
    op.alter_column('orders', 'status',
               existing_type=mysql.SET(collation='utf8_unicode_ci', length=11),
               type_=sa.Enum('pending', 'can_be_paid', 'po_created', 'paid', 'shipped', 'complete', name='orderstatus'),
               existing_nullable=True)
    op.create_foreign_key(None, 'orders', 'transactions', ['transaction_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'orders', type_='foreignkey')
    op.alter_column('orders', 'status',
               existing_type=sa.Enum('pending', 'can_be_paid', 'po_created', 'paid', 'shipped', 'complete', name='orderstatus'),
               type_=mysql.SET(collation='utf8_unicode_ci', length=11),
               existing_nullable=True)
    op.drop_column('orders', 'transaction_id')
    # ### end Alembic commands ###