"""order zip code

Revision ID: 4fd1a41b0133
Revises: d486c27d07cf
Create Date: 2020-12-23 16:56:13.061007

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4fd1a41b0133'
down_revision = 'd486c27d07cf'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('orders', sa.Column('zip', sa.String(length=10), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('orders', 'zip')
    # ### end Alembic commands ###