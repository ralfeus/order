"""invoice items

Revision ID: 7dbbe10c7ebb
Revises: 1dcf165c082b
Create Date: 2020-09-09 15:36:36.807735

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7dbbe10c7ebb'
down_revision = '1dcf165c082b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('invoice_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('when_created', sa.DateTime(), nullable=True),
    sa.Column('when_changed', sa.DateTime(), nullable=True),
    sa.Column('invoice_id', sa.String(length=16), nullable=True),
    sa.Column('product_id', sa.String(length=16), nullable=True),
    sa.Column('price', sa.Integer(), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invoice_items_when_created'), 'invoice_items', ['when_created'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_invoice_items_when_created'), table_name='invoice_items')
    op.drop_table('invoice_items')
    # ### end Alembic commands ###
