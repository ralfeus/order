"""order

Revision ID: 8caad29d2ae7
Revises: fb6787a7525a
Create Date: 2020-07-18 17:04:45.962293

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8caad29d2ae7'
down_revision = 'fb6787a7525a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('order_products',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=True),
    sa.Column('product_id', sa.String(length=16), nullable=True),
    sa.Column('subcustomer', sa.String(length=256), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=True),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('order_products')
    # ### end Alembic commands ###
