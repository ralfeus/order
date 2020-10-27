"""company - bank ID

Revision ID: 20ab3b1f8420
Revises: 716b2b1f0be6
Create Date: 2020-10-24 11:15:11.637612

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '20ab3b1f8420'
down_revision = '716b2b1f0be6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('companies', sa.Column('bank_id', sa.String(length=2), nullable=True))
    op.execute("UPDATE companies SET bank_id='06'")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('companies', 'bank_id')
    # ### end Alembic commands ###