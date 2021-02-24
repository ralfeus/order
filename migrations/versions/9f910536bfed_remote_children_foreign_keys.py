"""Remote children foreign keys

Revision ID: 9f910536bfed
Revises: 704e3a869e16
Create Date: 2021-02-24 20:04:53.429036

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '9f910536bfed'
down_revision = '704e3a869e16'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('network_nodes_ibfk_2', 'network_nodes', type_='foreignkey')
    op.drop_constraint('network_nodes_ibfk_3', 'network_nodes', type_='foreignkey')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_foreign_key('network_nodes_ibfk_3', 'network_nodes', 'network_nodes', ['right_id'], ['id'])
    op.create_foreign_key('network_nodes_ibfk_2', 'network_nodes', 'network_nodes', ['left_id'], ['id'])
    # ### end Alembic commands ###
