"""transaction

Revision ID: 5912b4c35c7a
Revises: a5da79b33042
Create Date: 2020-07-28 09:09:12.478041

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5912b4c35c7a'
down_revision = 'a5da79b33042'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('transactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('currency_code', sa.String(length=3), nullable=True),
    sa.Column('amount_orignal', sa.Float(), nullable=True),
    sa.Column('amount_krw', sa.Integer(), nullable=True),
    sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'cancelled', name='transactionstatus'), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('changed_at', sa.DateTime(), nullable=True),
    sa.Column('changed_by_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['currency_code'], ['currencies.code'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('transactions')
    # ### end Alembic commands ###
