"""po add vendor

Revision ID: 2a593c9fcb67
Revises: 5688f352e8d6
Create Date: 2020-11-20 09:10:57.890302

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2a593c9fcb67'
down_revision = '5688f352e8d6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('purchase_orders', sa.Column('vendor', sa.String(length=64), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('purchase_orders', 'vendor')
    # ### end Alembic commands ###
