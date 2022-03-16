"""currency enabled flag

Revision ID: 29831cf444c0
Revises: 9d7da9e4aece
Create Date: 2022-02-24 14:27:41.977682

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '29831cf444c0'
down_revision = '9d7da9e4aece'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('currencies', sa.Column('enabled', sa.Boolean(), nullable=True))
    op.execute("UPDATE currencies SET enabled=1")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('currencies', 'enabled')
    # ### end Alembic commands ###
