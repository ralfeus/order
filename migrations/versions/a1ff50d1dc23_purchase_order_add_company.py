"""purchase order add company

Revision ID: a1ff50d1dc23
Revises: e33cd5017043
Create Date: 2020-10-12 10:28:42.263818

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'a1ff50d1dc23'
down_revision = 'e33cd5017043'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('purchase_orders', sa.Column('company_id', sa.Integer(), nullable=True))
    op.alter_column('purchase_orders', 'status',
               existing_type=mysql.SET(collation='utf8_unicode_ci', length=9),
               type_=sa.Enum('pending', 'posted', 'paid', 'delivered', 'failed', name='purchaseorderstatus'),
               existing_nullable=True)
    op.create_foreign_key(None, 'purchase_orders', 'companies', ['company_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'purchase_orders', type_='foreignkey')
    op.alter_column('purchase_orders', 'status',
               existing_type=sa.Enum('pending', 'posted', 'paid', 'delivered', 'failed', name='purchaseorderstatus'),
               type_=mysql.SET(collation='utf8_unicode_ci', length=9),
               existing_nullable=True)
    op.drop_column('purchase_orders', 'company_id')
    # ### end Alembic commands ###