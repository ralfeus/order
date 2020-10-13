"""payment method: string -> object

Revision ID: 9fd17d9dcd45
Revises: bda39dafb2ed
Create Date: 2020-10-11 15:14:53.300060

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '9fd17d9dcd45'
down_revision = 'bda39dafb2ed'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('transactions', sa.Column('payment_method_id', sa.Integer(), nullable=True))
    op.execute("""
        UPDATE transactions SET payment_method_id = 1 
        WHERE payment_method = 'PayPal'
    """)
    op.execute("""
        UPDATE transactions SET payment_method_id = 2 
        WHERE payment_method = 'Wire transfer'
    """)
    op.create_foreign_key(None, 'transactions', 'payment_methods', ['payment_method_id'], ['id'])
    op.drop_column('transactions', 'payment_method')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('transactions', sa.Column('payment_method', mysql.VARCHAR(collation='utf8_unicode_ci', length=16), nullable=True))
    op.drop_constraint(None, 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'payment_method_id')
    # ### end Alembic commands ###