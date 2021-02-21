"""Network nodes

Revision ID: 47170d8c53fb
Revises: 02a0b7bd0fe5
Create Date: 2021-02-21 06:58:09.076611

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '47170d8c53fb'
down_revision = '02a0b7bd0fe5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_network_nodes_rank', table_name='network_nodes')
    op.drop_index('ix_network_nodes_when_created', table_name='network_nodes')
    op.drop_table('network_nodes')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('network_nodes',
    sa.Column('when_created', mysql.DATETIME(), nullable=True),
    sa.Column('when_changed', mysql.DATETIME(), nullable=True),
    sa.Column('id', mysql.VARCHAR(collation='utf8_unicode_ci', length=10), nullable=False),
    sa.Column('parent_id', mysql.VARCHAR(collation='utf8_unicode_ci', length=10), nullable=True),
    sa.Column('left_id', mysql.VARCHAR(collation='utf8_unicode_ci', length=10), nullable=True),
    sa.Column('right_id', mysql.VARCHAR(collation='utf8_unicode_ci', length=10), nullable=True),
    sa.Column('center', mysql.VARCHAR(collation='utf8_unicode_ci', length=64), nullable=True),
    sa.Column('country', mysql.VARCHAR(collation='utf8_unicode_ci', length=32), nullable=True),
    sa.Column('highest_rank', mysql.VARCHAR(collation='utf8_unicode_ci', length=16), nullable=True),
    sa.Column('name', mysql.VARCHAR(collation='utf8_unicode_ci', length=32), nullable=True),
    sa.Column('network_pv', mysql.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('pv', mysql.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('rank', mysql.VARCHAR(collation='utf8_unicode_ci', length=16), nullable=True),
    sa.Column('signup_date', sa.DATE(), nullable=True),
    sa.ForeignKeyConstraint(['left_id'], ['network_nodes.id'], name='network_nodes_ibfk_2'),
    sa.ForeignKeyConstraint(['parent_id'], ['network_nodes.id'], name='network_nodes_ibfk_1'),
    sa.ForeignKeyConstraint(['right_id'], ['network_nodes.id'], name='network_nodes_ibfk_3'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8_unicode_ci',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_network_nodes_when_created', 'network_nodes', ['when_created'], unique=False)
    op.create_index('ix_network_nodes_rank', 'network_nodes', ['rank'], unique=False)
    # ### end Alembic commands ###
