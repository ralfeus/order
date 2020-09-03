"""shipping polymorphic

Revision ID: 1dcf165c082b
Revises: 966e779b4f54
Create Date: 2020-09-03 07:42:24.766720

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1dcf165c082b'
down_revision = '966e779b4f54'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('shipping', sa.Column('discriminator', sa.String(length=50), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('shipping', 'discriminator')
    # ### end Alembic commands ###
