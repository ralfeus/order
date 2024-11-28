"""add country to Address instances

Revision ID: f822172d5329
Revises: ce6479cc2a8c
Create Date: 2024-11-18 11:41:02.941724

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'f822172d5329'
down_revision = 'ce6479cc2a8c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute("UPDATE addresses SET country_id='kr'")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # ### end Alembic commands ###
    pass