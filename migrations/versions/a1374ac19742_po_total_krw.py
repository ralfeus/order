"""PO total_krw

Revision ID: a1374ac19742
Revises: 502ab5d9b07f
Create Date: 2022-08-16 15:04:00.745483

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'a1374ac19742'
down_revision = '502ab5d9b07f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('orders', 'status',
               existing_type=mysql.SET(collation='utf8_unicode_ci', length=13),
               type_=sa.Enum('draft', 'pending', 'can_be_paid', 'po_created', 'packed', 'shipped', 'cancelled', 'ready_to_ship', 'at_warehouse', name='orderstatus'),
               existing_nullable=True)
    op.add_column('purchase_orders', sa.Column('total_krw', sa.Integer(), nullable=True))
    op.execute('''
        UPDATE             
            purchase_orders AS po JOIN (
                SELECT so.id, SUM(op.price * op.quantity) AS total_krw 
                FROM suborders AS so JOIN order_products AS op ON so.id = op.suborder_id 
                WHERE op.status <> 'unavailable' 
                GROUP BY so.id) AS so_total ON so_total.id = po.suborder_id 
        SET po.total_krw = so_total.total_krw 
    ''')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('purchase_orders', 'total_krw')
    op.alter_column('orders', 'status',
               existing_type=sa.Enum('draft', 'pending', 'can_be_paid', 'po_created', 'packed', 'shipped', 'cancelled', 'ready_to_ship', 'at_warehouse', name='orderstatus'),
               type_=mysql.SET(collation='utf8_unicode_ci', length=13),
               existing_nullable=True)
    # ### end Alembic commands ###