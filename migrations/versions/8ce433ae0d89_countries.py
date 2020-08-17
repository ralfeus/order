"""countries

Revision ID: 8ce433ae0d89
Revises: b069a204d962
Create Date: 2020-08-17 13:52:33.681439

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '8ce433ae0d89'
down_revision = 'b069a204d962'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('shipping_rates', 'destination',
               existing_type=mysql.VARCHAR(collation='utf8_unicode_ci', length=32),
               type_=sa.String(length=2),
               existing_nullable=True)
    op.drop_index('ix_shipping_rates_destination', table_name='shipping_rates')
    op.create_foreign_key(None, 'shipping_rates', 'countries', ['destination'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'shipping_rates', type_='foreignkey')
    op.create_index('ix_shipping_rates_destination', 'shipping_rates', ['destination'], unique=False)
    op.alter_column('shipping_rates', 'destination',
               existing_type=sa.String(length=2),
               type_=mysql.VARCHAR(collation='utf8_unicode_ci', length=32),
               existing_nullable=True)
    # ### end Alembic commands ###
