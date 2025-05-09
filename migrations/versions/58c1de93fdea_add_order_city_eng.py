"""add order.city_eng

Revision ID: 58c1de93fdea
Revises: 8e6aa0006bd6
Create Date: 2024-11-16 15:51:52.777589

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '58c1de93fdea'
down_revision = '8e6aa0006bd6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('orders', sa.Column('city_eng', sa.String(length=128), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('orders', 'city_eng')
    # ### end Alembic commands ###
