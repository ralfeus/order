"""payment methods poly

Revision ID: 9e94c8112ac6
Revises: 4127588062a6
Create Date: 2021-09-02 17:37:04.338144

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9e94c8112ac6'
down_revision = '4127588062a6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('payment_methods', sa.Column('discriminator', sa.String(length=50), nullable=True))
    op.execute("UPDATE payment_methods SET discriminator='paypal' WHERE name='PayPal'")
    op.execute("UPDATE payment_methods SET discriminator='swift' WHERE name LIKE '%SWIFT%'")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('payments', 'discriminator')
    # ### end Alembic commands ###
