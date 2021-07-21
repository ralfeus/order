"""warehouse

Revision ID: b724fe040186
Revises: 5a9a1e0450a6
Create Date: 2021-07-20 15:43:23.294683

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b724fe040186'
down_revision = '5a9a1e0450a6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('warehouses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('when_created', sa.DateTime(), nullable=True),
    sa.Column('when_changed', sa.DateTime(), nullable=True),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('is_local', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_warehouses_when_created'), 'warehouses', ['when_created'], unique=False)
    op.create_table('warehouse_products',
    sa.Column('warehouse_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.String(length=16), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ),
    sa.PrimaryKeyConstraint('warehouse_id', 'product_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('warehouse_products')
    op.drop_index(op.f('ix_warehouses_when_created'), table_name='warehouses')
    op.drop_table('warehouses')
    # ### end Alembic commands ###
