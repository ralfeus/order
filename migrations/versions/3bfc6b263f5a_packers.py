"""packers

Revision ID: 3bfc6b263f5a
Revises: a1374ac19742
Create Date: 2022-10-31 19:45:28.929782

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '3bfc6b263f5a'
down_revision = 'a1374ac19742'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('packers',
    sa.Column('when_created', sa.DateTime(), nullable=True),
    sa.Column('when_changed', sa.DateTime(), nullable=True),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.PrimaryKeyConstraint('name')
    )
    op.create_index(op.f('ix_packers_when_created'), 'packers', ['when_created'], unique=False)
    op.create_table('order_packers',
    sa.Column('when_created', sa.DateTime(), nullable=True),
    sa.Column('when_changed', sa.DateTime(), nullable=True),
    sa.Column('order_id', sa.String(length=16), nullable=False),
    sa.Column('packer', sa.String(length=128), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.ForeignKeyConstraint(['packer'], ['packers.name'], ),
    sa.PrimaryKeyConstraint('order_id', 'packer')
    )
    op.create_index(op.f('ix_order_packers_when_created'), 'order_packers', ['when_created'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_order_packers_when_created'), table_name='order_packers')
    op.drop_table('order_packers')
    op.drop_index(op.f('ix_packers_when_created'), table_name='packers')
    op.drop_table('packers')
    # ### end Alembic commands ###