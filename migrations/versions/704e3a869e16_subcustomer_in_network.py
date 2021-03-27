"""Subcustomer: in_network

Revision ID: 704e3a869e16
Revises: a181924e78bd
Create Date: 2021-02-23 10:33:06.363315

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '704e3a869e16'
down_revision = 'a181924e78bd'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('subcustomers', sa.Column('in_network', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('subcustomers', 'in_network')
    # ### end Alembic commands ###