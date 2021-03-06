"""order-to-transaction

Revision ID: 38bd2ff9a112
Revises: 74595706728d
Create Date: 2020-09-28 13:32:01.526316

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '38bd2ff9a112'
down_revision = '74595706728d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('transactions_orders',
    sa.Column('transaction_id', sa.Integer(), nullable=True),
    sa.Column('order_id', sa.String(16), nullable=True),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], )
    )
    op.create_index(op.f('ix_transactions_when_created'), 'transactions', ['when_created'], unique=False)
    op.drop_constraint('transactions_ibfk_4', 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'order_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('transactions', sa.Column('order_id', mysql.VARCHAR(collation='utf8_unicode_ci', length=16), nullable=True))
    op.create_foreign_key('transactions_ibfk_4', 'transactions', 'orders', ['order_id'], ['id'])
    op.drop_index(op.f('ix_transactions_when_created'), table_name='transactions')
    op.drop_table('transactions_orders')
    # ### end Alembic commands ###
