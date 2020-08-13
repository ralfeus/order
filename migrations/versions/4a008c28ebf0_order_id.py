"""order id

Revision ID: 4a008c28ebf0
Revises: deaf42a8c083
Create Date: 2020-08-13 08:04:48.454528

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '4a008c28ebf0'
down_revision = 'deaf42a8c083'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('order_products_ibfk_1', 'order_products', type_='foreignkey')
    op.alter_column('order_products', 'order_id',
               existing_type=mysql.INTEGER(),
               type_=sa.String(length=16),
               existing_nullable=True)
    op.alter_column('orders', 'id',
               existing_type=mysql.INTEGER(),
               type_=sa.String(length=16),
               nullable=False)
    op.create_foreign_key('order_products_ibfk_1', 'order_products', 'orders', ['order_id'], ['id'])
    op.add_column('orders', sa.Column('seq_num', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('order_products_ibfk_1', 'order_products', type_='foreignkey')
    op.alter_column('orders', 'id',
               existing_type=sa.String(length=16),
               type_=mysql.INTEGER())
    op.alter_column('order_products', 'order_id',
               existing_type=sa.String(length=16),
               type_=mysql.INTEGER(),
               existing_nullable=False)
    op.create_foreign_key('order_products_ibfk_1', 'order_products', 'orders', ['order_id'], ['id'])
    op.drop_column('orders', 'seq_num')
    # ### end Alembic commands ###
