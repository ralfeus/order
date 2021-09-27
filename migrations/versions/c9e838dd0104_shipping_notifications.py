"""shipping notifications

Revision ID: c9e838dd0104
Revises: 9e94c8112ac6
Create Date: 2021-09-17 16:58:22.911288

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9e838dd0104'
down_revision = '9e94c8112ac6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('shipping', sa.Column('notification', sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('shipping', 'notification')
    # ### end Alembic commands ###
