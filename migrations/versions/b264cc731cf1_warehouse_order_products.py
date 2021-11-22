"""warehouse order products

Revision ID: b264cc731cf1
Revises: c9e838dd0104
Create Date: 2021-10-16 12:24:40.918312

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b264cc731cf1'
down_revision = 'c9e838dd0104'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('order_products_warehouses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('when_created', sa.DateTime(), nullable=True),
    sa.Column('when_changed', sa.DateTime(), nullable=True),
    sa.Column('order_product_id', sa.Integer(), nullable=True),
    sa.Column('warehouse_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['order_product_id'], ['order_products.id'], ),
    sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_products_warehouses_when_created'), 'order_products_warehouses', ['when_created'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_order_products_warehouses_when_created'), table_name='order_products_warehouses')
    op.drop_table('order_products_warehouses')
    # ### end Alembic commands ###
