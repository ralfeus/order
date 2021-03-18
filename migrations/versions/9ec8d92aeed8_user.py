"""user

Revision ID: 9ec8d92aeed8
Revises: e7708754c392
Create Date: 2021-03-03 18:16:48.692193

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9ec8d92aeed8'
down_revision = 'e7708754c392'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('atomy_id', sa.String(length=10), nullable=True))
    op.add_column('users', sa.Column('phone', sa.String(length=16), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'phone')
    op.drop_column('users', 'atomy_id')
    # ### end Alembic commands ###
