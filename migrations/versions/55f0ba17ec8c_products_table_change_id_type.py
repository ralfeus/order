"""products table change id type

Revision ID: 55f0ba17ec8c
Revises: b9fb1bf1aa6a
Create Date: 2020-07-16 11:53:14.632306

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '55f0ba17ec8c'
down_revision = 'b9fb1bf1aa6a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('products', sa.Column('product_id', sa.String(length=64), nullable=False))
    op.drop_column('products', 'id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('products', sa.Column('id', mysql.INTEGER(), autoincrement=False, nullable=False))
    op.drop_column('products', 'product_id')
    # ### end Alembic commands ###
